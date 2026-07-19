"""Lightweight retrieval types (no heavy imports — safe for the ports module)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class VectorHit(BaseModel):
    id: str
    text: str
    metadata: dict[str, Any]
    distance: float  # smaller = closer
