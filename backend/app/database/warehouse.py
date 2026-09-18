import os
import subprocess
import sys
from pathlib import Path

import psycopg
from sqlalchemy.engine import make_url

from backend.app.core.config import Settings

ROOT = Path(__file__).resolve().parents[3]


def build_warehouse(settings: Settings) -> None:
    url = make_url(settings.sqlalchemy_url)
    env = os.environ | {
        "DBT_HOST": url.host or "localhost",
        "DBT_PORT": str(url.port or 5432),
        "DBT_USER": url.username or "",
        "DBT_ENV_SECRET_PASSWORD": url.password or "",
        "DBT_DATABASE": url.database or "",
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
    }
    with psycopg.connect(settings.psycopg_url, autocommit=True, connect_timeout=10) as connection:
        locked = connection.execute("SELECT pg_try_advisory_lock(72513044)").fetchone()
        if not locked or not locked[0]:
            raise RuntimeError("Another warehouse build is running")
        subprocess.run(
            [
                str(Path(sys.executable).with_name("dbt")),
                "build",
                "--project-dir",
                str(ROOT / "dbt"),
                "--profiles-dir",
                str(ROOT / "dbt"),
                "--no-use-colors",
            ],
            cwd=ROOT,
            env=env,
            check=True,
        )


if __name__ == "__main__":
    build_warehouse(Settings())
