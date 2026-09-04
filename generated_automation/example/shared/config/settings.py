"""Global test automation configuration settings."""
import os
from dataclasses import dataclass

@dataclass
class Settings:
    BASE_URL: str = os.getenv("APP_BASE_URL", "https://example.com/")
    HEADLESS: bool = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes")
    DEFAULT_TIMEOUT: int = int(os.getenv("DEFAULT_TIMEOUT", "10000"))
    SLOW_MO: int = int(os.getenv("SLOW_MO", "0"))
    SCREENSHOT_ON_FAILURE: bool = True

settings = Settings()
