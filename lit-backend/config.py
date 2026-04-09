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

    @property
    def cors_origins(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if self.ALLOWED_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance to avoid reloading .env on every request."""
    return Settings()
