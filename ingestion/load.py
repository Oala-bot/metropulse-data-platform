import argparse
import gzip
import json
import logging
import os
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TextIO, cast
from uuid import UUID, uuid4

import pandas as pd
import psycopg
from psycopg import sql
from pydantic import ValidationError

from backend.app.core.config import Settings
from ingestion.clean import clean_batch
from ingestion.download import checksum, download, source_url
from ingestion.validate import COLUMN_MAP, validate_schema
from ingestion.zones import Zone, download_zones, read_zones

LOGGER = logging.getLogger(__name__)
LOAD_LOCK = 72513042
TRIP_COLUMNS = [
    "trip_key",
    "load_batch_id",
    "source_row",
    "source_year",
    "source_month",
    *COLUMN_MAP.values(),
    "duration_seconds",
]
INTEGER_COLUMNS = [
    "source_row",
    "source_year",
    "source_month",
    "vendor_id",
    "pickup_zone_id",
    "dropoff_zone_id",
    "payment_type",
    "passenger_count",
    "rate_code",
]


def write_quarantine(file: TextIO, rows: pd.DataFrame) -> None:
    if not rows.empty:
        file.write(rows.to_json(orient="records", lines=True, date_format="iso", date_unit="us"))


def load_zones(connection: psycopg.Connection[Any], zones: list[Zone]) -> set[int]:
    with connection.cursor() as cursor:
        cursor.executemany(
            """INSERT INTO staging.zone(location_id, borough, zone, service_zone)
               VALUES (%s, %s, %s, %s) ON CONFLICT (location_id) DO UPDATE
               SET borough = EXCLUDED.borough, zone = EXCLUDED.zone,
                   service_zone = EXCLUDED.service_zone""",
            [(z.location_id, z.borough, z.zone, z.service_zone) for z in zones],
        )
    return {
        z.location_id
        for z in zones
        if z.location_id not in {264, 265} and z.borough not in {"Unknown", "N/A"}
    }


def insert_trips(
    connection: psycopg.Connection[Any], frame: pd.DataFrame, batch_id: UUID, year: int, month: int
) -> set[int]:
    if frame.empty:
        return set()
    frame = frame.assign(load_batch_id=str(batch_id), source_year=year, source_month=month)
    for column in INTEGER_COLUMNS:
        frame[column] = frame[column].astype("Int64")
    connection.execute("TRUNCATE incoming")
    statement = sql.SQL("COPY incoming ({}) FROM STDIN WITH (FORMAT CSV, NULL '\\N')").format(
        sql.SQL(",").join(map(sql.Identifier, TRIP_COLUMNS))
    )
    with connection.cursor() as cursor, cursor.copy(statement) as copy:
        copy.write(frame[TRIP_COLUMNS].to_csv(index=False, header=False, na_rep="\\N"))
    inserted = connection.execute("""
        INSERT INTO staging.trip SELECT * FROM incoming ORDER BY source_row
        ON CONFLICT (trip_key) DO NOTHING RETURNING source_row
    """).fetchall()
    return {int(row[0]) for row in inserted}


def load_month(
    path: Path, year: int, month: int, settings: Settings, zones_path: Path | None = None
) -> dict[str, Any]:
    source_url(year, month)
    batch_id = uuid4()
    source_checksum = checksum(path)
    counts = {"rows_read": 0, "rows_accepted": 0, "rows_rejected": 0, "duplicate_rows": 0}
    rule_counts: Counter[str] = Counter()
    settings.rejected_data_dir.mkdir(parents=True, exist_ok=True)
    quarantine = settings.rejected_data_dir / f"{year}-{month:02d}-{batch_id}.jsonl.gz"
    temporary = quarantine.with_suffix(".gz.part")
    with psycopg.connect(settings.psycopg_url, autocommit=True, connect_timeout=10) as connection:
        locked = connection.execute("SELECT pg_try_advisory_lock(%s)", (LOAD_LOCK,)).fetchone()
        if not locked or not locked[0]:
            raise RuntimeError("Another ingestion is running; try again after it finishes")
        try:
            # A process killed mid-load loses its lock and transaction, but keeps its audit row.
            connection.execute("""
                UPDATE load_batch SET status='failed', finished_at=now(),
                    failure_message='Previous loader exited before completing the transaction'
                WHERE status='running'
            """)
            connection.execute(
                """
                INSERT INTO load_batch(
                    id,source_file,source_checksum,source_year,source_month,status
                )
                VALUES (%s,%s,%s,%s,%s,'running')
            """,
                (batch_id, path.name, source_checksum, year, month),
            )
            try:
                prior = connection.execute(
                    """
                    SELECT id FROM load_batch WHERE source_checksum=%s AND status='succeeded'
                    AND source_year=%s AND source_month=%s
                """,
                    (source_checksum, year, month),
                ).fetchone()
                if prior:
                    connection.execute(
                        "UPDATE load_batch SET status='skipped',finished_at=now() WHERE id=%s",
                        (batch_id,),
                    )
                    return {
                        "batch_id": str(batch_id),
                        "status": "skipped",
                        "previous_batch_id": str(prior[0]),
                        **counts,
                    }
                parquet = validate_schema(path)
                zones = (
                    read_zones(zones_path)
                    if zones_path
                    else download_zones(settings.raw_data_dir / "taxi_zone_lookup.csv")
                )
                with connection.transaction():
                    zone_ids = load_zones(connection, zones)
                    connection.execute(
                        "CREATE TEMP TABLE incoming (LIKE staging.trip) ON COMMIT DROP"
                    )
                    with gzip.open(temporary, "wt", encoding="utf-8") as rejected_file:
                        for batch in parquet.iter_batches(batch_size=settings.ingestion_batch_size):
                            raw = batch.to_pandas()
                            offset = counts["rows_read"]
                            cleaned = clean_batch(raw, zone_ids, year, month, offset)
                            counts["rows_read"] += len(raw)
                            rule_counts.update(cleaned.rule_counts)
                            inserted = insert_trips(
                                connection, cleaned.accepted, batch_id, year, month
                            )
                            duplicates = cleaned.accepted.loc[
                                ~cleaned.accepted["source_row"].isin(inserted), "source_row"
                            ]
                            raw["source_row"] = range(offset + 1, offset + len(raw) + 1)
                            duplicate_rows = raw.loc[raw["source_row"].isin(duplicates)].copy()
                            duplicate_rows["rejection_reasons"] = [["duplicate_trip_key"]] * len(
                                duplicate_rows
                            )
                            counts["rows_accepted"] += len(inserted)
                            counts["rows_rejected"] += len(cleaned.rejected)
                            counts["duplicate_rows"] += len(duplicate_rows)
                            rule_counts["duplicate_trip_key"] += len(duplicate_rows)
                            write_quarantine(rejected_file, cleaned.rejected)
                            write_quarantine(rejected_file, duplicate_rows)
                            LOGGER.info(json.dumps({"batch_id": str(batch_id), **counts}))
                    if checksum(path) != source_checksum:
                        raise RuntimeError(
                            "Source file changed during ingestion; no trips were committed"
                        )
                    os.replace(temporary, quarantine)
                    with connection.cursor() as cursor:
                        cursor.executemany(
                            """INSERT INTO data_quality_result(load_batch_id,rule,failed_rows)
                               VALUES (%s,%s,%s)""",
                            [(batch_id, rule, count) for rule, count in rule_counts.items()],
                        )
                    connection.execute(
                        """
                        UPDATE load_batch SET status='succeeded',finished_at=now(),rows_read=%s,
                        rows_accepted=%s,rows_rejected=%s,duplicate_rows=%s,quarantine_path=%s
                        WHERE id=%s
                    """,
                        (*counts.values(), str(quarantine.resolve()), batch_id),
                    )
            except Exception as exc:
                if temporary.exists():
                    os.replace(temporary, quarantine)
                failure = failure_message(exc)
                connection.execute(
                    """
                    UPDATE load_batch SET status='failed',finished_at=now(),rows_read=%s,
                    rows_accepted=0,rows_rejected=%s,duplicate_rows=%s,
                    failure_message=%s,quarantine_path=%s WHERE id=%s
                """,
                    (
                        counts["rows_read"],
                        counts["rows_rejected"],
                        counts["duplicate_rows"],
                        failure,
                        str(quarantine.resolve()) if quarantine.exists() else None,
                        batch_id,
                    ),
                )
                raise
        finally:
            connection.execute("SELECT pg_advisory_unlock(%s)", (LOAD_LOCK,))
    return {
        "batch_id": str(batch_id),
        "status": "succeeded",
        **counts,
        "quarantine_path": str(quarantine),
        "finished_at": datetime.now(UTC).isoformat(),
    }


def failure_message(exc: Exception) -> str:
    if isinstance(exc, psycopg.Error):
        return (
            f"Database error ({exc.sqlstate or type(exc).__name__}); "
            "check connection and migrations"
        )
    if isinstance(exc, ValidationError):
        return "; ".join(
            f"{'.'.join(map(str, error['loc']))}: {error['msg']}"
            for error in exc.errors(include_input=False)
        )
    return str(exc)[:2000]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate, quarantine, and load a Yellow Taxi month."
    )
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--file", type=Path)
    parser.add_argument("--zones", type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        settings = Settings()
        source_url(args.year, args.month)
        path = cast(Path | None, args.file)
        if path is None:
            result = download(
                args.year,
                args.month,
                output_dir=settings.raw_data_dir,
                base_url=settings.tlc_base_url,
            )
            path = Path(result.destination)
        result_info = load_month(path, args.year, args.month, settings, args.zones)
        print(json.dumps(result_info))
        return 0
    except Exception as exc:
        LOGGER.error("Ingestion failed: %s", failure_message(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
