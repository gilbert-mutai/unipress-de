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

    # Source-document provenance for output attribution (best-effort; empty => skip).
    manifest_path: str = Field(default="data/manifest.yaml")

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

    # Mount prefix when the api is served behind a path-stripping proxy
    # (production: nginx routes /api/* -> api:8000/*). FastAPI needs it to build
    # correct absolute links — without it /api/docs asks for /openapi.json at the
    # site root, which nginx hands to the frontend. Empty in local dev.
    root_path: str = Field(default="")

    # LLM. Extraction defaults to the deterministic heuristic; the LLM path is
    # opt-in (requires BOTH the flag and a key) so no spend happens by accident.
    openai_api_key: str = Field(default="")
    llm_extraction: bool = Field(default=False)
    llm_generation: bool = Field(default=False)
    llm_extract_model: str = Field(default="gpt-4o-mini")
    llm_judge_model: str = Field(default="gpt-4o-mini")
    llm_generation_model: str = Field(default="gpt-4o")

    # TrustLayer. nli_backend: "lexical" (proxy, default) | "nli" (mDeBERTa XNLI).
    nli_backend: str = Field(default="lexical")
    nli_model: str = Field(default="MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7")
    llm_judge: bool = Field(default=False)  # Tier-2 judge, opt-in (needs a key)
    trust_w1: float = Field(default=0.4)  # entailment weight
    trust_w2: float = Field(default=0.4)  # judge supported-fraction weight
    trust_w3: float = Field(default=0.2)  # quote overlap weight
    trust_numeric_penalty: float = Field(default=0.6)
    trust_export_threshold: float = Field(default=0.7)
    trust_low_threshold: float = Field(default=0.45)
    trust_entail_high: float = Field(default=0.85)  # skip judge if entail above this
    trust_contradict_cutoff: float = Field(default=0.5)  # NLI contradiction => hard fail

    @property
    def otel_enabled(self) -> bool:
        return bool(self.otel_exporter_otlp_endpoint)


@lru_cache
def get_settings() -> Settings:
    return Settings()
