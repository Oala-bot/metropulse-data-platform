import argparse
import json
from pathlib import Path
from typing import Any

import pyarrow.compute as pc
import pyarrow.parquet as pq


def profile(path: Path) -> dict[str, Any]:
    parquet = pq.ParquetFile(path)
    nulls = dict.fromkeys(parquet.schema_arrow.names, 0)
    ranges: dict[str, dict[str, Any]] = {}
    negative_counts = dict.fromkeys(["trip_distance", "fare_amount", "total_amount"], 0)
    pickup_not_before_dropoff = 0
    for batch in parquet.iter_batches(batch_size=65536):
        for name in batch.schema.names:
            column = batch.column(name)
            nulls[name] += column.null_count
            if name in {"tpep_pickup_datetime", "tpep_dropoff_datetime", *negative_counts}:
                limits = pc.min_max(column).as_py()
                if limits["min"] is not None:
                    prior = ranges.get(name)
                    ranges[name] = {
                        "min": min(prior["min"], limits["min"]) if prior else limits["min"],
                        "max": max(prior["max"], limits["max"]) if prior else limits["max"],
                    }
            if name in negative_counts:
                negative_counts[name] += pc.sum(pc.less(column, 0)).as_py() or 0
        pickup_not_before_dropoff += (
            pc.sum(
                pc.greater_equal(
                    batch.column("tpep_pickup_datetime"), batch.column("tpep_dropoff_datetime")
                )
            ).as_py()
            or 0
        )
    return {
        "source_file": path.name,
        "rows": parquet.metadata.num_rows,
        "row_groups": parquet.metadata.num_row_groups,
        "schema": {field.name: str(field.type) for field in parquet.schema_arrow},
        "null_counts": nulls,
        "ranges": ranges,
        "negative_counts": negative_counts,
        "pickup_not_before_dropoff": pickup_not_before_dropoff,
        "note": "Raw observations; anomaly counts overlap and are not quarantine decisions.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile a monthly TLC Parquet file.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = profile(args.path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, default=str) + "\n")
    print(f"Profiled {report['rows']:,} rows -> {args.output}")


if __name__ == "__main__":
    main()
