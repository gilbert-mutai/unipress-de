"""Port definitions (structural typing via Protocol)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class VectorStore(Protocol):
    """Embedding index. Graduation path: in-memory stub -> Chroma -> Qdrant."""

    def upsert(self, doc_id: str, chunks: list[str]) -> int: ...

    def query(self, text: str, k: int = 5) -> list[str]: ...


@runtime_checkable
class LLMGateway(Protocol):
    """Text generation. Graduation path: echo stub -> LiteLLM(OpenAI/Ollama)."""

    def complete(self, prompt: str, **kwargs: object) -> str: ...


@runtime_checkable
class Storage(Protocol):
    """Blob storage for uploads/outputs. Graduation path: local FS -> MinIO/S3."""

    def put(self, key: str, data: bytes) -> str: ...

    def get(self, key: str) -> bytes: ...


@runtime_checkable
class TaskDispatch(Protocol):
    """Async job dispatch. Graduation path: Celery (documented as swappable)."""

    def enqueue_pipeline(self, job_id: str) -> str: ...

    def enqueue_ingestion(self, job_id: str, document_id: str) -> str: ...
