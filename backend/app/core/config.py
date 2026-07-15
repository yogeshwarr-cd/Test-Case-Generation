from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    app_name: str = "Test Case Generator"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8001
    debug: bool = True
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/testcase_generator"
    backend_1_integration_mode: str = "database"
    backend_1_api_url: str = "http://localhost:8000/api/v1"
    backend_1_database_url: str | None = None
    cors_origins: list[str] = ["http://localhost:3000"]

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
