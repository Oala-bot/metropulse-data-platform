from alembic import context
from sqlalchemy import create_engine, pool

from backend.app.core.config import Settings

settings = Settings()


def run_migrations() -> None:
    if context.is_offline_mode():
        context.configure(url=settings.sqlalchemy_url, literal_binds=True)
        with context.begin_transaction():
            context.run_migrations()
    else:
        engine = create_engine(settings.sqlalchemy_url, poolclass=pool.NullPool)
        with engine.connect() as connection:
            context.configure(connection=connection)
            with context.begin_transaction():
                context.run_migrations()
        engine.dispose()


run_migrations()
