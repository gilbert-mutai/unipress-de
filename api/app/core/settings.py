"""Typed, env-driven configuration (12-factor). Invalid config fails fast at boot."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = Field(default="development")
    log_level: str = Field(default="INFO")

    # Data services (compose provides these; sensible local defaults otherwise).
    database_url: str = Field(
        default="postgresql+psycopg://unipress:unipress@localhost:5432/unipress"
    )
    redis_url: str = Field(default="redis://localhost:6379/0")

    # Blob storage root for uploaded PDFs + parse artifacts (shared api/worker volume).
    storage_root: str = Field(default="./var/storage")

    # Observability. Empty endpoint => OTLP export disabled (spans stay no-op).
    otel_service_name: str = Field(default="unipress")
    otel_exporter_otlp_endpoint: str = Field(default="")

    # CORS. In production the frontend + api share one origin behind nginx, so
    # this stays empty; local dev needs the frontend origin allowed.
    cors_origins: list[str] = Field(default=["http://localhost:3000"])

    # LLM (unused until the generation phase).
    openai_api_key: str = Field(default="")

    @property
    def otel_enabled(self) -> bool:
        return bool(self.otel_exporter_otlp_endpoint)


@lru_cache
def get_settings() -> Settings:
    return Settings()
