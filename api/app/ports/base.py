"""Port definitions (structural typing via Protocol)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from app.retrieval.types import VectorHit


@runtime_checkable
class VectorStore(Protocol):
    """Embedding index over precomputed vectors. Graduation: in-memory -> Chroma -> Qdrant."""

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> int: ...

    def query(
        self, embedding: list[float], k: int = 5, where: dict[str, Any] | None = None
    ) -> list[VectorHit]: ...

    def delete(self, where: dict[str, Any]) -> None: ...


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
