"""In-memory brute-force vector store — used by tests and single-process local runs.

Not shared across processes, so compose uses Chroma instead. Kept because it lets
the whole retrieval path run with zero external services.
"""

from __future__ import annotations

from typing import Any

from app.retrieval.types import VectorHit


def _cosine_distance(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    return 1.0 - dot  # vectors are L2-normalized upstream


def _matches(meta: dict[str, Any], where: dict[str, Any] | None) -> bool:
    return where is None or all(meta.get(k) == v for k, v in where.items())


class InMemoryVectorStore:
    def __init__(self) -> None:
        self._items: dict[str, tuple[list[float], str, dict[str, Any]]] = {}

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> int:
        for i, emb, doc, meta in zip(ids, embeddings, documents, metadatas, strict=True):
            self._items[i] = (emb, doc, meta)
        return len(ids)

    def query(
        self, embedding: list[float], k: int = 5, where: dict[str, Any] | None = None
    ) -> list[VectorHit]:
        scored = [
            VectorHit(id=i, text=doc, metadata=meta, distance=_cosine_distance(embedding, emb))
            for i, (emb, doc, meta) in self._items.items()
            if _matches(meta, where)
        ]
        scored.sort(key=lambda h: h.distance)
        return scored[:k]

    def delete(self, where: dict[str, Any]) -> None:
        for i in [i for i, (_, _, meta) in self._items.items() if _matches(meta, where)]:
            del self._items[i]
