"""Hexagonal ports — the interfaces infrastructure must satisfy.

The domain depends on these Protocols, never on concrete infra, so Chroma,
OpenAI, S3, or Celery are swappable adapters. Phase 0 ships stub adapters
(see app/adapters/) so the skeleton runs end-to-end without real infra.
"""

from app.ports.base import LLMGateway, Storage, TaskDispatch, VectorStore

__all__ = ["VectorStore", "LLMGateway", "Storage", "TaskDispatch"]
