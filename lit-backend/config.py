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

    # Outcome model — which prediction populates the top-level
    # SimulationResponse.result: "new_model" (trained binary classifier)
    # or "old_heuristic" (hand-picked weights). Automatically forced to
    # "old_heuristic" if the trained model fails to load, regardless of
    # this setting. Flip via env var for a fast, code-free revert.
    OUTCOME_MODEL_PRIMARY: str = "new_model"
    OUTCOME_MODEL_PATH: str = ""  # Optional gated, versioned artifact path
    PRECEDENT_INDEX_PATH: str = ""  # Optional dated precedent index used by live search

    # Case chat — instruction-tuned generation model, called through HF's
    # OpenAI-compatible chat-completions router (multi-provider, generally
    # better free-tier availability for conversational models than the
    # older single-provider api-inference.huggingface.co/models/<id> path
    # that embedder.py/extractor.py use for embeddings/NER). Override via
    # env var if this model becomes unavailable — no code change needed.
    # Verified live against the real account 2026-09-25 — Qwen2.5-7B-Instruct
    # and several other candidates (Mistral-7B-Instruct-v0.3, zephyr-7b-beta,
    # Phi-3.5-mini-instruct, gemma-2-9b-it) came back "not supported by any
    # provider you have enabled" for this account; Llama-3.1-8B-Instruct and
    # Qwen2.5-72B-Instruct both worked. Picked the 8B model for lower demo
    # latency over the 72B one.
    CHAT_MODEL: str = "meta-llama/Llama-3.1-8B-Instruct"
    CHAT_TOP_K: int = 5

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
