"""Chroma-backed vector store (the production `VectorStore`).

Uses an HTTP client when `chroma_url` is set (compose), otherwise a local
persistent client at `chroma_path`. `chromadb` is imported lazily so tests that
use the in-memory store never require it. Embeddings are computed upstream by the
`Embedder`; this adapter only stores/queries vectors.
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.retrieval.types import VectorHit

log = get_logger("retrieval.chroma")

_COLLECTION = "chunks"


class ChromaVectorStore:
    def __init__(self, url: str = "", path: str = "./var/chroma") -> None:
        import chromadb

        client: Any
        if url:
            host, _, port = url.replace("http://", "").replace("https://", "").partition(":")
            client = chromadb.HttpClient(host=host or "localhost", port=int(port or 8000))
            log.info("chroma.http", host=host, port=port)
        else:
            client = chromadb.PersistentClient(path=path)
            log.info("chroma.persistent", path=path)
        # We supply our own embeddings, so no collection embedding function.
        # Typed as Any: chromadb's stubs are strict; calls are runtime-validated.
        self._col: Any = client.get_or_create_collection(
            _COLLECTION, metadata={"hnsw:space": "cosine"}
        )

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict[str, Any]],
    ) -> int:
        if not ids:
            return 0
        self._col.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
        return len(ids)

    def query(
        self, embedding: list[float], k: int = 5, where: dict[str, Any] | None = None
    ) -> list[VectorHit]:
        res = self._col.query(query_embeddings=[embedding], n_results=k, where=where or None)
        hits: list[VectorHit] = []
        ids = res.get("ids", [[]])[0]
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        for i, doc, meta, dist in zip(ids, docs, metas, dists, strict=False):
            hits.append(VectorHit(id=i, text=doc, metadata=meta or {}, distance=float(dist)))
        return hits

    def delete(self, where: dict[str, Any]) -> None:
        self._col.delete(where=where)
