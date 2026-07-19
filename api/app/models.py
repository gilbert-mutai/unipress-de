"""Pydantic API contracts. The richer claim/span models arrive in the pipeline phase."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


class JobCreate(BaseModel):
    # Placeholder input for the skeleton; becomes an uploaded document in Phase 1.
    input_text: str = Field(default="hello unipress", max_length=10_000)


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: JobStatus
    stage: str
    input_text: str
    document_id: str | None = None
    result: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    status: JobStatus
    page_count: int | None = None
    chunk_count: int | None = None
    language: str | None = None
    warnings: list[str] | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime


class ChunkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    index: int
    page: int
    section: str | None = None
    char_start: int
    char_end: int
    bbox: list[float] | None = None
    text: str
    token_estimate: int
