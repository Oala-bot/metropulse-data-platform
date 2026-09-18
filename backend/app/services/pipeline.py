import os
import subprocess
import sys
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Connection, text

from backend.app.core.config import Settings
from backend.app.database.warehouse import ROOT

JOB_LOCK = 72513043
RUN_SELECT = """
    SELECT r.*,
        extract(epoch FROM coalesce(r.finished_at, now()) - r.started_at) AS duration_seconds,
        CASE WHEN b.id IS NULL THEN NULL ELSE jsonb_build_object(
            'id', b.id, 'source_file', b.source_file, 'status', b.status,
            'rows_read', b.rows_read, 'rows_accepted', b.rows_accepted,
            'rows_rejected', b.rows_rejected, 'duplicate_rows', b.duplicate_rows,
            'started_at', b.started_at, 'finished_at', b.finished_at,
            'failure_message', b.failure_message
        ) END AS load_batch
    FROM pipeline_run r LEFT JOIN load_batch b ON b.id = r.load_batch_id
"""


def list_runs(connection: Connection, limit: int, offset: int) -> dict[str, Any]:
    total = connection.execute(text("SELECT count(*) FROM pipeline_run")).scalar_one()
    rows = connection.execute(
        text(RUN_SELECT + " ORDER BY r.started_at DESC, r.id LIMIT :limit OFFSET :offset"),
        {"limit": limit, "offset": offset},
    )
    latest = (
        connection.execute(
            text(
                "SELECT * FROM load_batch WHERE status='succeeded' "
                "ORDER BY finished_at DESC, id LIMIT 1"
            )
        )
        .mappings()
        .first()
    )
    return {
        "latest_successful_load": dict(latest) if latest else None,
        "items": [dict(row) for row in rows.mappings()],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def get_run(connection: Connection, run_id: UUID) -> dict[str, Any] | None:
    row = (
        connection.execute(text(RUN_SELECT + " WHERE r.id=:id"), {"id": run_id}).mappings().first()
    )
    return dict(row) if row else None


def enqueue(connection: Connection, year: int, month: int, settings: Settings) -> UUID:
    locked = connection.execute(
        text("SELECT pg_try_advisory_xact_lock(:lock)"), {"lock": JOB_LOCK}
    ).scalar_one()
    if not locked:
        raise RuntimeError("Another ingestion pipeline is running")
    # A worker holds JOB_LOCK until exit; a running row without the lock is stale.
    connection.execute(
        text("""UPDATE pipeline_run SET status='failed',finished_at=now(),
        failure_message='Worker exited before completing the run'
        WHERE status='running' OR
            (status='queued' AND started_at < now() - interval '5 minutes')""")
    )
    if connection.execute(text("SELECT 1 FROM pipeline_run WHERE status='queued' LIMIT 1")).first():
        raise RuntimeError("An ingestion pipeline is already queued")
    run_id = uuid4()
    connection.execute(
        text("""INSERT INTO pipeline_run(id,status,source_year,source_month,task_states)
        VALUES (:id,'queued',:year,:month,
            '{"download":"pending","load":"pending","warehouse":"pending"}')"""),
        {"id": run_id, "year": year, "month": month},
    )
    connection.commit()
    log_dir = ROOT / "logs"
    try:
        log_dir.mkdir(exist_ok=True)
        env = os.environ | {
            "DATABASE_URL": settings.database_url.get_secret_value(),
            "RAW_DATA_DIR": str(settings.raw_data_dir.resolve()),
            "REJECTED_DATA_DIR": str(settings.rejected_data_dir.resolve()),
            "TLC_BASE_URL": settings.tlc_base_url,
            "INGESTION_BATCH_SIZE": str(settings.ingestion_batch_size),
        }
        with (log_dir / f"ingest-{run_id}.log").open("ab") as log:
            subprocess.Popen(
                [sys.executable, "-m", "backend.app.services.ingest", str(run_id)],
                cwd=ROOT,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
    except OSError:
        connection.execute(
            text("""UPDATE pipeline_run SET status='failed',finished_at=now(),
            failure_message='Could not start ingestion worker' WHERE id=:id"""),
            {"id": run_id},
        )
        connection.commit()
        raise
    return run_id
