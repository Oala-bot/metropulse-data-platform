from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: SecretStr
    tlc_base_url: str = "https://d37ci6vzurychx.cloudfront.net/trip-data"
    raw_data_dir: Path = Path("data/raw")
    rejected_data_dir: Path = Path("data/rejected")
    admin_api_key: SecretStr | None = None
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    ingestion_batch_size: int = Field(default=50_000, ge=1, le=250_000)

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: SecretStr) -> SecretStr:
        try:
            url = make_url(value.get_secret_value())
        except Exception:
            raise ValueError("DATABASE_URL must be a PostgreSQL connection URL") from None
        if url.drivername not in {"postgresql", "postgresql+psycopg"} or not url.database:
            raise ValueError("DATABASE_URL must specify a PostgreSQL database")
        return value

    @property
    def sqlalchemy_url(self) -> str:
        return (
            make_url(self.database_url.get_secret_value())
            .set(drivername="postgresql+psycopg")
            .render_as_string(hide_password=False)
        )

    @property
    def psycopg_url(self) -> str:
        return (
            make_url(self.database_url.get_secret_value())
            .set(drivername="postgresql")
            .render_as_string(hide_password=False)
        )
