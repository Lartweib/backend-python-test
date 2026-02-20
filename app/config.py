"""Configuration from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings. Reads from env vars; defaults work for local/Docker."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Env vars: PROVIDER_URL, PROVIDER_API_KEY (or NOTIFICATION_PROVIDER_URL, etc.)
    provider_url: str = "http://localhost:3001"
    provider_api_key: str = "test-dev-2026"
    provider_timeout_seconds: float = 10.0
    provider_retry_attempts: int = 3
    provider_retry_min_wait: float = 0.5
    provider_retry_max_wait: float = 4.0


settings = Settings()
