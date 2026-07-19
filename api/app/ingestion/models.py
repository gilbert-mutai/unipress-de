"""Ingestion data contracts (Pydantic).

`SourceSpan` follows docs/03 §1.1 — it is the traceability backbone: every chunk
(and later, every claim) carries the exact page/section/offset/quote/bbox so the
UI can highlight the source. `Claim`/`GeneratedSentence` (docs/03 §1.2–1.3) arrive
with the claim-extraction slice (Phase 1b).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SourceSpan(BaseModel):
    """Where a piece of text lives in the source document (docs/03 §1.1)."""

    doc_id: str
    page: int  # 1-indexed
    section: str | None = None
    char_start: int  # offset into the section's normalized text
    char_end: int
    quote: str  # the exact supporting text, verbatim
    bbox: list[float] | None = None  # [x0, y0, x1, y1] for UI highlight, if available


class Block(BaseModel):
    """A text block from the parser (a paragraph-ish unit with a bounding box)."""

    text: str
    bbox: list[float]  # [x0, y0, x1, y1]


class Page(BaseModel):
    """One parsed page: its blocks plus whether it looked image-only (needs OCR)."""

    number: int  # 1-indexed
    text: str
    blocks: list[Block] = Field(default_factory=list)
    image_only: bool = False


class ParsedDoc(BaseModel):
    """The full parser output for a document."""

    doc_id: str
    filename: str
    page_count: int
    pages: list[Page]
    warnings: list[str] = Field(default_factory=list)

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.text for p in self.pages)


class Chunk(BaseModel):
    """A retrieval/generation unit with full provenance back to the source."""

    index: int  # order within the document
    text: str
    span: SourceSpan
    token_estimate: int = 0
