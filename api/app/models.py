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
    stage: str | None = None  # latest pipeline stage (parse/chunk/extract/embed/done)
    progress: int | None = None  # 0–100, derived from the stage
    page_count: int | None = None
    chunk_count: int | None = None
    claim_count: int | None = None
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


class ClaimRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    key: str
    text: str
    claim_type: str
    page: int
    section: str | None = None
    char_start: int
    char_end: int
    quote: str
    bbox: list[float] | None = None
    entities: list[str] | None = None
    importance: float
    numeric: bool


class SearchQuery(BaseModel):
    query: str = Field(min_length=1, max_length=1000)
    k: int = Field(default=8, ge=1, le=50)


class SearchHit(BaseModel):
    chunk_id: str
    page: int
    section: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    score: float  # 1 - distance (higher = more relevant)
    text: str


class GenerateRequest(BaseModel):
    output_type: str = Field(default="PRESS_RELEASE")
    language: str = Field(default="en", pattern="^(en|hu)$")
    # Reuse an existing output for this (document, type, language) when one
    # exists — the demo-safety path. Set true to force a new generation.
    refresh: bool = Field(default=False)


class SentenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_index: int
    text: str
    role: str
    claim_ids: list[str] | None = None
    section: str | None = None
    timecode: str | None = None
    on_screen: str | None = None
    visual: str | None = None
    verdict: str | None = None
    confidence: float | None = None
    rationale: str | None = None


class OutputSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    output_type: str
    language: str
    title: str
    title_claim_ids: list[str] | None = None
    title_verdict: str | None = None
    title_confidence: float | None = None
    title_rationale: str | None = None
    status: JobStatus
    created_at: datetime


class OutputDetail(OutputSummary):
    coverage: dict | None = None
    sentences: list[SentenceRead] = []
