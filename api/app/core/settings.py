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

    # Retrieval / embeddings.
    #   embed_backend: "sentence-transformers" (real) | "hashing" (deterministic, tests)
    #   embed_model: multilingual-e5-small by default (HU+EN, ~470MB); BGE-M3 is a
    #   drop-in swap on the VM (docs/07 §2.2). embed_dim only used by the hashing stub.
    embed_backend: str = Field(default="sentence-transformers")
    embed_model: str = Field(default="intfloat/multilingual-e5-small")
    embed_dim: int = Field(default=384)
    # Vector store: "chroma" (HTTP when chroma_url set, else local persistent at
    # chroma_path) or "memory" (single-process; tests).
    vector_backend: str = Field(default="chroma")
    chroma_url: str = Field(default="")
    chroma_path: str = Field(default="./var/chroma")
    retrieval_top_k: int = Field(default=8)

    # Observability. Empty endpoint => OTLP export disabled (spans stay no-op).
    otel_service_name: str = Field(default="unipress")
    otel_exporter_otlp_endpoint: str = Field(default="")

    # CORS. In production the frontend + api share one origin behind nginx, so
    # this stays empty; local dev needs the frontend origin allowed.
    cors_origins: list[str] = Field(default=["http://localhost:3000"])

    # LLM. Extraction defaults to the deterministic heuristic; the LLM path is
    # opt-in (requires BOTH the flag and a key) so no spend happens by accident.
    openai_api_key: str = Field(default="")
    llm_extraction: bool = Field(default=False)
    llm_extract_model: str = Field(default="gpt-4o-mini")
    llm_judge_model: str = Field(default="gpt-4o-mini")
    llm_generation_model: str = Field(default="gpt-4o")

    @property
    def otel_enabled(self) -> bool:
        return bool(self.otel_exporter_otlp_endpoint)


@lru_cache
def get_settings() -> Settings:
    return Settings()
