"""Ingestion orchestration used by the Celery pipeline (kept out of tasks for testability).

Stages persist their output so each is idempotent and re-loadable without passing
large blobs through the broker:
  parse  -> writes parsed.json to storage, sets Document.page_count/warnings
  chunk  -> reads parsed.json, writes Chunk rows, sets Document.chunk_count
"""

from __future__ import annotations

from app.adapters.stubs import LocalStorage
from app.core.db import session_scope
from app.core.logging import get_logger
from app.db_models import Chunk, Document
from app.ingestion.chunker import chunk_document
from app.ingestion.models import ParsedDoc
from app.ingestion.parser import parse_pdf

log = get_logger("ingestion.service")


def _parsed_key(document_id: str) -> str:
    return f"{document_id}/parsed.json"


def parse_stage(document_id: str) -> None:
    """Load the raw PDF, parse it, persist the parsed artifact + page metadata."""
    storage = LocalStorage()
    with session_scope() as s:
        doc = s.get(Document, document_id)
        if doc is None:
            raise ValueError(f"document {document_id} not found")
        content_key = doc.content_key

    data = storage.get(content_key)
    parsed = parse_pdf(data, doc_id=document_id, filename=content_key.split("/")[-1])
    storage.put(_parsed_key(document_id), parsed.model_dump_json().encode("utf-8"))

    with session_scope() as s:
        doc = s.get(Document, document_id)
        assert doc is not None
        doc.page_count = parsed.page_count
        doc.warnings = parsed.warnings or None


def chunk_stage(document_id: str) -> int:
    """Load the parsed artifact, chunk it, persist Chunk rows. Returns chunk count."""
    storage = LocalStorage()
    parsed = ParsedDoc.model_validate_json(storage.get(_parsed_key(document_id)).decode("utf-8"))
    chunks = chunk_document(parsed)

    with session_scope() as s:
        # Idempotency: clear any prior chunks for this document before reinserting.
        doc = s.get(Document, document_id)
        assert doc is not None
        doc.chunks.clear()
        s.flush()
        for c in chunks:
            s.add(
                Chunk(
                    document_id=document_id,
                    index=c.index,
                    page=c.span.page,
                    section=c.span.section,
                    char_start=c.span.char_start,
                    char_end=c.span.char_end,
                    bbox=c.span.bbox,
                    text=c.text,
                    token_estimate=c.token_estimate,
                )
            )
        doc.chunk_count = len(chunks)
    log.info("chunked", document_id=document_id, chunks=len(chunks))
    return len(chunks)
