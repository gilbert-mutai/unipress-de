"""Retrieval orchestration: embed a document's chunks, and search them.

`embed_stage` runs in the worker (Celery `embed` stage); `search` runs in the api
(synchronous). Both share the embedder + vector store via process-level singletons.
"""

from __future__ import annotations

from app.core.db import session_scope
from app.core.logging import get_logger
from app.core.metrics import timed_stage
from app.core.settings import get_settings
from app.db_models import Chunk as ChunkRow
from app.ports import VectorStore
from app.retrieval.embedder import get_embedder
from app.retrieval.types import VectorHit

log = get_logger("retrieval.service")

_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    global _store
    if _store is None:
        settings = get_settings()
        if settings.vector_backend == "memory":
            from app.retrieval.memory_store import InMemoryVectorStore

            _store = InMemoryVectorStore()
        else:
            from app.retrieval.chroma_store import ChromaVectorStore

            _store = ChromaVectorStore(url=settings.chroma_url, path=settings.chroma_path)
    return _store


def reset_vector_store() -> None:
    """Test hook: drop the cached store so settings changes take effect."""
    global _store
    _store = None


def _metadata(row: ChunkRow) -> dict[str, object]:
    meta: dict[str, object] = {
        "document_id": row.document_id,
        "chunk_index": row.index,
        "page": row.page,
        "char_start": row.char_start,
        "char_end": row.char_end,
    }
    if row.section:  # Chroma rejects None metadata values
        meta["section"] = row.section
    return meta


@timed_stage("embed")
def embed_stage(document_id: str) -> int:
    """Embed a document's chunks into the vector store (idempotent). Returns count."""
    with session_scope() as s:
        rows = (
            s.query(ChunkRow)
            .filter(ChunkRow.document_id == document_id)
            .order_by(ChunkRow.index)
            .all()
        )
        ids = [r.id for r in rows]
        texts = [r.text for r in rows]
        metadatas = [_metadata(r) for r in rows]

    store = get_vector_store()
    store.delete({"document_id": document_id})
    if not ids:
        return 0
    embeddings = get_embedder().embed_passages(texts)
    store.add(ids, embeddings, texts, metadatas)
    log.info("embedded", document_id=document_id, chunks=len(ids))
    return len(ids)


def search(document_id: str, query: str, k: int | None = None) -> list[VectorHit]:
    """Semantic search over a document's chunks."""
    k = k or get_settings().retrieval_top_k
    embedding = get_embedder().embed_query(query)
    return get_vector_store().query(embedding, k=k, where={"document_id": document_id})
