import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # pydantic-settings normally JSON-decodes complex fields before field
        # validators run. Disabling that lets one explicit parser reliably
        # support both JSON arrays and developer-friendly comma-separated text.
        enable_decoding=False,
    )
    app_name: str = "Test Case Generator"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8001
    debug: bool = True
    database_url: str = (
        "postgresql://neondb_owner:npg_PXIsV9S7dJWB@ep-billowing-grass-atkw4nta-pooler.c-9.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    )
    database_connect_timeout: float = 30.0
    backend_1_integration_mode: str = "database"
    backend_1_api_url: str = "http://localhost:8000/api/v1"
    backend_1_database_url: str | None = None
    cors_origins: list[str] = Field(default_factory=list)
    groq_api_key: str = ""
    groq_model: str = ""
    gemini_api_key: str = ""
    gemini_model: str = ""
    openai_api_key: str = ""
    openai_model: str = ""
    llm_primary_provider: str = "groq"
    llm_fallback_providers: list[str] = Field(default_factory=lambda: ["gemini", "openai"])
    llm_request_timeout_seconds: float = 60.0
    llm_temperature: float = 0.2
    llm_max_output_tokens: int = 6000
    llm_provider_retry_count: int = 1

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
        """Parse JSON arrays, comma-separated origins, or a single origin."""
        if isinstance(value, str):
            raw_value = value.strip()
            if not raw_value:
                return []
            if raw_value.startswith("["):
                parsed = json.loads(raw_value)
                if not isinstance(parsed, list):
                    raise ValueError("CORS_ORIGINS JSON value must be an array")
                return [str(origin).strip() for origin in parsed if str(origin).strip()]
            return [origin.strip() for origin in raw_value.split(",") if origin.strip()]
        return value

    @field_validator("llm_fallback_providers", mode="before")
    @classmethod
    def parse_provider_names(cls, value: object) -> object:
        if isinstance(value, str):
            return [name.strip().lower() for name in value.split(",") if name.strip()]
        return value

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
