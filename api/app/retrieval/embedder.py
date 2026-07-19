"""Embedding backends behind a small port.

- SentenceTransformerEmbedder: the real backend. Default model is
  multilingual-e5-small (HU + EN, ~470MB); set EMBED_MODEL=BAAI/bge-m3 on the VM
  for the documented production default (docs/07 §2.2). torch/sentence-transformers
  are imported lazily so nothing heavy loads unless a real embed is requested.
- HashingEmbedder: a deterministic, dependency-free stub used by tests/CI so the
  retrieval pipeline runs with no model download.
"""

from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Protocol, runtime_checkable

from app.core.logging import get_logger
from app.core.settings import get_settings

log = get_logger("retrieval.embedder")
_TOKEN = re.compile(r"\w+", re.UNICODE)


@runtime_checkable
class Embedder(Protocol):
    @property
    def dim(self) -> int: ...

    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def _needs_e5_prefix(model: str) -> bool:
    return "e5" in model.lower()


class SentenceTransformerEmbedder:
    def __init__(self, model: str) -> None:
        self.model_name = model
        self._e5 = _needs_e5_prefix(model)
        self._model: Any = None  # lazy

    def _load(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            log.info("embedder.load", model=self.model_name)
            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def dim(self) -> int:
        return int(self._load().get_sentence_embedding_dimension())

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._load().encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vectors]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        if self._e5:
            texts = [f"passage: {t}" for t in texts]
        return self._encode(texts)

    def embed_query(self, text: str) -> list[float]:
        if self._e5:
            text = f"query: {text}"
        return self._encode([text])[0]


class HashingEmbedder:
    """Deterministic bag-of-hashed-tokens vector (lexical similarity). Tests only."""

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * self.dim
        for tok in _TOKEN.findall(text.lower()):
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)  # noqa: S324 - not security
            v[h % self.dim] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


_embedder: Embedder | None = None


def _build_embedder() -> Embedder:
    settings = get_settings()
    if settings.embed_backend == "hashing":
        return HashingEmbedder(settings.embed_dim)
    return SentenceTransformerEmbedder(settings.embed_model)


def get_embedder() -> Embedder:
    global _embedder
    emb = _embedder
    if emb is None:
        emb = _build_embedder()
        _embedder = emb
    return emb


def reset_embedder() -> None:
    """Test hook: drop the cached embedder so settings changes take effect."""
    global _embedder
    _embedder = None
