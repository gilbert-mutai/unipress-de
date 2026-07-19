"""In-memory / trivial adapters so the skeleton runs without real infra.

Each is replaced by a production adapter in a later phase, behind the same port:
  InMemoryVectorStore -> ChromaVectorStore
  EchoLLM             -> LiteLLMGateway
  LocalStorage        -> S3Storage
  CeleryTaskDispatch  -> (kept; Celery is the production choice)
"""

from __future__ import annotations

from pathlib import Path


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._store: dict[str, list[str]] = {}

    def upsert(self, doc_id: str, chunks: list[str]) -> int:
        self._store.setdefault(doc_id, []).extend(chunks)
        return len(chunks)

    def query(self, text: str, k: int = 5) -> list[str]:
        hits = [c for chunks in self._store.values() for c in chunks if text.lower() in c.lower()]
        return hits[:k]


class EchoLLM:
    def complete(self, prompt: str, **kwargs: object) -> str:
        return f"[echo] {prompt}"


class LocalStorage:
    def __init__(self, root: str = "/tmp/unipress-storage") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, key: str, data: bytes) -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def get(self, key: str) -> bytes:
        return (self.root / key).read_bytes()


class CeleryTaskDispatch:
    """Adapter over the Celery pipeline entrypoint (imported lazily to avoid cycles)."""

    def enqueue_pipeline(self, job_id: str) -> str:
        from app.tasks.chains import start_pipeline

        return start_pipeline(job_id)
