from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Hugging Face Configuration
    HUGGINGFACE_API_KEY: str = ""

    # Kanoon API Configuration
    KANOON_BASE_URL: str = "https://api.kanoon.example.com/v1"

    # CORS Configuration
    ALLOWED_ORIGINS: str = "*"

    # Server Configuration
    PORT: int = 8000

    # Logging
    LOG_LEVEL: str = "INFO"

    # Cache
    CACHE_TTL: int = 3600

    # App Metadata
    APP_NAME: str = "Legal Intelligence Terminal"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Environment
    ENV: str = "development"

    # Use fixtures (offline dev mode)
    USE_FIXTURES: bool = False

    @property
    def IS_PRODUCTION(self) -> bool:
        """True when running in production environment."""
        return self.ENV == "production"

    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string.

        In development (default): if ALLOWED_ORIGINS is "*", allow all origins.
        In production: only explicit origins from ALLOWED_ORIGINS.
          If set to "*" in production, defaults to empty list (no CORS access).
        """
        if not self.IS_PRODUCTION and self.ALLOWED_ORIGINS == "*":
            return ["*"]
        if self.ALLOWED_ORIGINS == "*":
            # In production, never allow wildcard — safest default
            return []
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_origins_list(self) -> List[str]:
        """Always return the parsed list (no wildcard fallback)."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def hf_key_set(self) -> bool:
        """Whether the HF API key is configured (safe to log)."""
        return bool(self.HUGGINGFACE_API_KEY and not self.HUGGINGFACE_API_KEY.startswith("hf_your_"))

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance to avoid reloading .env on every request."""
    return Settings()
