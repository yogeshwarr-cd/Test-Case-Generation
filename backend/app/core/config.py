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
    app_port: int = 8003
    debug: bool = True
    app_mock_mode: bool = False  # TODO: re-enable mock mode when needed
    database_url: str = (
        "postgresql://neondb_owner:npg_PXIsV9S7dJWB@ep-billowing-grass-atkw4nta-pooler.c-9.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    )
    database_connect_timeout: float = 30.0
    redis_cache_enabled: bool = True
    redis_url: str = "redis://127.0.0.1:6379/0"
    redis_key_prefix: str = "testcase-generator:v1"
    redis_connect_timeout_seconds: float = 2.0
    redis_workflow_ttl_seconds: int = 86400
    redis_script_ttl_seconds: int = 86400
    backend_1_integration_mode: str = "database"
    backend_1_api_url: str = "http://localhost:8000/api/v1"
    backend_1_database_url: str | None = None
    cors_origins: list[str] = Field(default_factory=list)
    cerebras_api_key: str = ""
    cerebras_fallback_api_key: str = ""
    cerebras_model: str = "gpt-oss-120b"
    cerebras_fallback_model: str = ""
    cerebras_generation_model: str = ""
    cerebras_validation_model: str = ""
    cerebras_regeneration_model: str = ""
    llm_request_timeout_seconds: float = 45.0
    llm_temperature: float = 0.2
    llm_max_output_tokens: int = 6000
    llm_generation_max_output_tokens: int = 1500
    llm_validation_max_output_tokens: int = 2000
    llm_regeneration_max_output_tokens: int = 3000
    llm_structured_output_repair_enabled: bool = False
    llm_scenario_batch_size: int = 5
    llm_testcase_batch_size: int = 4
    cerebras_max_concurrent_requests: int = 1
    cerebras_provider_retry_count: int = 0
    cerebras_initial_backoff_seconds: float = 2.0
    cerebras_max_backoff_seconds: float = 10.0
    cerebras_min_request_interval_seconds: float = 15.0
    cerebras_quota_cooldown_seconds: float = 60.0
    llm_provider_retry_count: int = 3
    llm_rate_limit_backoff_seconds: float = 2.0
    llm_rate_limit_jitter_seconds: float = 0.25
    image_upload_enabled: bool = True
    image_max_size_mb: int = 10
    image_max_width: int = 4096
    image_max_height: int = 4096
    image_allowed_types: str = "image/png,image/jpeg,image/webp"
    image_storage_backend: str = "local"
    image_storage_path: str = "./storage/images"
    ocr_provider: str = "paddleocr"
    ocr_language: str = "en"
    ocr_min_confidence: float = 0.60
    ui_detector_provider: str = "yolo"
    yolo_model_path: str = "./ml/models/ui_detector.onnx"
    yolo_min_confidence: float = 0.50
    yolo_iou_threshold: float = 0.45
    yolo_device: str = "cpu"
    enable_heuristic_ui_detection: bool = True
    enable_vision_llm_fallback: bool = False
    vision_llm_min_local_confidence: float = 0.60
    vision_llm_max_calls_per_image: int = 1
    image_analysis_cache_enabled: bool = True
    image_analysis_cache_ttl_seconds: int = 604800
    llm_rate_limit_fallback_threshold_seconds: float = 10.0
    automation_artifacts_path: str = "./artifacts/automation"
    automation_navigation_timeout_seconds: float = 30.0
    automation_action_timeout_seconds: float = 10.0
    automation_navigation_settle_timeout_seconds: float = 3.0
    automation_wait_for_network_idle: bool = False
    automation_defect_confidence_threshold: float = 0.80
    automation_require_reproducible_failure: bool = True
    automation_crawl_page_limit: int = 20
    automation_crawl_depth_limit: int = 5
    skyvern_fallback_enabled: bool = False
    skyvern_integration_mode: str = "self_hosted"
    skyvern_base_url: str = "http://localhost:8000"
    skyvern_api_key: str = ""
    skyvern_timeout_seconds: float = 30.0
    skyvern_max_attempts: int = 1
    skyvern_max_calls_per_test: int = 2
    skyvern_max_calls_per_run: int = 20

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

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
