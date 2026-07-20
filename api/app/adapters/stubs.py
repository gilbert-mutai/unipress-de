"""Trivial adapters so the skeleton runs without real infra.

Each is replaced by a production adapter behind the same port:
  EchoLLM      -> LiteLLMGateway (app/llm/gateway.py, done)
  LocalStorage -> S3Storage
  CeleryTaskDispatch -> (kept; Celery is the production choice)
The VectorStore adapters live in app/retrieval/ (InMemoryVectorStore, ChromaVectorStore).
"""

from __future__ import annotations

from pathlib import Path


class EchoLLM:
    def complete(self, prompt: str, **kwargs: object) -> str:
        return f"[echo] {prompt}"


class LocalStorage:
    def __init__(self, root: str | None = None) -> None:
        from app.core.settings import get_settings

        self.root = Path(root or get_settings().storage_root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, data: bytes) -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def get(self, key: str) -> bytes:
        return (self.root / key).read_bytes()


class CeleryTaskDispatch:
    """Adapter over the Celery pipeline entrypoints (imported lazily to avoid cycles)."""

    def enqueue_pipeline(self, job_id: str) -> str:
        from app.tasks.chains import start_pipeline

        return start_pipeline(job_id)

    def enqueue_ingestion(self, job_id: str, document_id: str) -> str:
        from app.tasks.chains import start_ingestion

        return start_ingestion(job_id, document_id)

    def enqueue_generation(
        self, job_id: str, document_id: str, output_type: str, language: str
    ) -> str:
        from app.tasks.chains import start_generation

        return start_generation(job_id, document_id, output_type, language)
