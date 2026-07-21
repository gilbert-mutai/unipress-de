"""Claim extraction orchestration used by the Celery pipeline.

Reads a document's persisted chunks, runs the configured extractor (heuristic by
default; LLM path opt-in via settings.llm_extraction), and persists the resulting
quote-verified claims. Extraction is idempotent — prior claims are cleared first.
"""

from __future__ import annotations

from app.claims.heuristic import extract_claims
from app.claims.models import Claim as ClaimModel
from app.core.db import session_scope
from app.core.logging import get_logger
from app.core.metrics import timed_stage
from app.core.settings import get_settings
from app.db_models import Chunk as ChunkRow
from app.db_models import Claim as ClaimRow
from app.db_models import Document
from app.ingestion.models import Chunk, SourceSpan

log = get_logger("claims.service")


def _chunk_rows_to_models(rows: list[ChunkRow]) -> list[Chunk]:
    return [
        Chunk(
            index=r.index,
            text=r.text,
            token_estimate=r.token_estimate,
            span=SourceSpan(
                doc_id=r.document_id,
                page=r.page,
                section=r.section,
                char_start=r.char_start,
                char_end=r.char_end,
                quote=r.text,
                bbox=r.bbox,
            ),
        )
        for r in rows
    ]


def _run_extractor(chunks: list[Chunk]) -> list[ClaimModel]:
    settings = get_settings()
    if settings.llm_extraction and settings.openai_api_key:
        from app.claims.llm_extractor import extract_claims_llm

        log.info("extract.llm", model=settings.llm_extract_model)
        return extract_claims_llm(chunks)
    return extract_claims(chunks)


@timed_stage("extract")
def extract_stage(document_id: str) -> int:
    """Extract + persist claims for a document. Returns the claim count."""
    with session_scope() as s:
        rows = (
            s.query(ChunkRow)
            .filter(ChunkRow.document_id == document_id)
            .order_by(ChunkRow.index)
            .all()
        )
        chunks = _chunk_rows_to_models(rows)

    claims = _run_extractor(chunks)

    with session_scope() as s:
        doc = s.get(Document, document_id)
        if doc is None:
            raise ValueError(f"document {document_id} not found")
        doc.claims.clear()
        s.flush()
        for c in claims:
            s.add(
                ClaimRow(
                    document_id=document_id,
                    key=c.key,
                    text=c.text,
                    claim_type=c.claim_type.value,
                    page=c.span.page,
                    section=c.span.section,
                    char_start=c.span.char_start,
                    char_end=c.span.char_end,
                    quote=c.span.quote,
                    bbox=c.span.bbox,
                    entities=c.entities or None,
                    importance=c.importance,
                    numeric=c.numeric,
                )
            )
        doc.claim_count = len(claims)
    log.info("extracted", document_id=document_id, claims=len(claims))
    return len(claims)
