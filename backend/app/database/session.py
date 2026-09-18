from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Connection, Engine, create_engine

from backend.app.core.config import Settings


def create_database_engine(settings: Settings) -> Engine:
    return create_engine(
        settings.sqlalchemy_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=30000"},
    )


def database(request: Request) -> Iterator[Connection]:
    with request.app.state.engine.connect() as connection:
        yield connection
