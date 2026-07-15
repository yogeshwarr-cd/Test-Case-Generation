from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "Test Case Generator"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8001
    debug: bool = True
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/testcase_generator"
    )
    backend_1_integration_mode: str = "database"
    backend_1_api_url: str = "http://localhost:8000/api/v1"
    backend_1_database_url: str | None = None
    cors_origins: list[str] = ["http://localhost:3000"]

    @field_validator("database_url", "backend_1_database_url", mode="before")
    @classmethod
    def normalize_async_database_url(cls, value: object) -> object:
        """Convert standard PostgreSQL URLs into SQLAlchemy asyncpg URLs."""
        if not isinstance(value, str) or not value:
            return value

        parsed = urlsplit(value)
        if parsed.scheme not in {"postgres", "postgresql", "postgresql+psycopg2"}:
            return value

        query = []
        for key, query_value in parse_qsl(parsed.query, keep_blank_values=True):
            if key == "channel_binding":
                continue
            query.append(("ssl" if key == "sslmode" else key, query_value))

        return urlunsplit(
            ("postgresql+asyncpg", parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
        )

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug(cls, value: object) -> object:
        """Accept common environment labels in addition to boolean strings."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod", "off", "no"}:
                return False
            if normalized in {"development", "dev", "debug", "on", "yes"}:
                return True
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str) and not value.startswith("["):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
