import json
import logging
import sys
from pathlib import Path
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb

from backend.app.core.config import Settings
from backend.app.database.warehouse import build_warehouse
from backend.app.services.pipeline import JOB_LOCK
from ingestion.download import download
from ingestion.load import failure_message, load_month


def execute_run(run_id: UUID, settings: Settings) -> None:
    tasks = {"download": "pending", "load": "pending", "warehouse": "pending"}
    stage = "download"
    with psycopg.connect(settings.psycopg_url, autocommit=True, connect_timeout=10) as connection:
        lock = connection.execute("SELECT pg_try_advisory_lock(%s)", (JOB_LOCK,)).fetchone()
        if not lock or not lock[0]:
            connection.execute(
                """UPDATE pipeline_run SET status='failed',finished_at=now(),
                failure_message='Another ingestion pipeline is running' WHERE id=%s""",
                (run_id,),
            )
            return
        try:
            row = connection.execute(
                """UPDATE pipeline_run SET status='running' WHERE id=%s
                AND status='queued' RETURNING source_year,source_month""",
                (run_id,),
            ).fetchone()
            if row is None:
                return
            year, month = row
            tasks[stage] = "running"
            connection.execute(
                "UPDATE pipeline_run SET task_states=%s WHERE id=%s", (Jsonb(tasks), run_id)
            )
            result = download(
                year, month, output_dir=settings.raw_data_dir, base_url=settings.tlc_base_url
            )
            tasks[stage] = "succeeded"
            stage = "load"
            tasks[stage] = "running"
            connection.execute(
                "UPDATE pipeline_run SET task_states=%s WHERE id=%s", (Jsonb(tasks), run_id)
            )
            batch = load_month(Path(result.destination), year, month, settings)
            tasks[stage] = "skipped" if batch["status"] == "skipped" else "succeeded"
            connection.execute(
                "UPDATE pipeline_run SET load_batch_id=%s,task_states=%s WHERE id=%s",
                (batch.get("previous_batch_id", batch["batch_id"]), Jsonb(tasks), run_id),
            )
            stage = "warehouse"
            tasks[stage] = "running"
            connection.execute(
                "UPDATE pipeline_run SET task_states=%s WHERE id=%s", (Jsonb(tasks), run_id)
            )
            build_warehouse(settings)
            tasks[stage] = "succeeded"
            connection.execute(
                """UPDATE pipeline_run SET status='succeeded',finished_at=now(),
                task_states=%s WHERE id=%s""",
                (Jsonb(tasks), run_id),
            )
        except Exception as exc:
            if stage == "load":
                connection.execute(
                    """UPDATE pipeline_run SET load_batch_id=(
                    SELECT id FROM load_batch WHERE source_checksum=%s
                    AND source_year=%s AND source_month=%s
                    AND started_at >= (SELECT started_at FROM pipeline_run WHERE id=%s)
                    ORDER BY started_at DESC LIMIT 1
                ) WHERE id=%s""",
                    (result.checksum, year, month, run_id, run_id),
                )
            tasks[stage] = "failed"
            connection.execute(
                """UPDATE pipeline_run SET status='failed',finished_at=now(),
                task_states=%s,failure_message=%s WHERE id=%s""",
                (Jsonb(tasks), failure_message(exc), run_id),
            )
            logging.error(
                json.dumps(
                    {
                        "run_id": str(run_id),
                        "status": "failed",
                        "stage": stage,
                        "error": failure_message(exc),
                    }
                )
            )
            raise
        finally:
            connection.execute("SELECT pg_advisory_unlock(%s)", (JOB_LOCK,))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    execute_run(UUID(sys.argv[1]), Settings())
