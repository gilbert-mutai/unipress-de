"""FastAPI dependencies (injection points, overridable in tests)."""

from __future__ import annotations

from app.adapters.stubs import LocalStorage
from app.ports import Storage


def get_storage() -> Storage:
    """Blob storage for uploads. Rooted at settings.storage_root."""
    return LocalStorage()
