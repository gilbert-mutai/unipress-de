"""Celery chains: the real ingestion and generation pipelines.

The Phase 0 demo chain (a Job walked through stand-in stages with no document)
was removed along with its only caller, POST /jobs — everything here now
operates on a real document.
"""

from __future__ import annotations

from celery import chain

from app.core.db import session_scope
from app.core.logging import get_logger
from app.db_models import Job
from app.tasks.celery_app import celery

log = get_logger("tasks")


def _set(job_id: str, **fields: object) -> None:
    with session_scope() as s:
        job = s.get(Job, job_id)
        if job is None:
            raise ValueError(f"job {job_id} not found")
        for key, value in fields.items():
            setattr(job, key, value)


# --- Real ingestion pipeline (Phase 1): parse a PDF into a span-linked claim store.
# Stages will grow (extract, embed) in Phase 1b/1c; for now: ingest -> parse -> chunk.


def _fail(job_id: str, document_id: str, exc: Exception) -> None:
    _set(job_id, status="failed", error=str(exc))
    _set_document(document_id, status="failed", error=str(exc))


@celery.task(name="ingest.parse")
def task_parse(job_id: str, document_id: str) -> str:
    from app.ingestion.service import parse_stage

    _set(job_id, status="processing", stage="parse")
    _set_document(document_id, status="processing")
    try:
        parse_stage(document_id)
    except Exception as exc:
        _fail(job_id, document_id, exc)
        raise
    return job_id


@celery.task(name="ingest.chunk")
def task_chunk(prev: object, job_id: str, document_id: str) -> str:
    from app.ingestion.service import chunk_stage

    _set(job_id, stage="chunk")
    try:
        n = chunk_stage(document_id)
    except Exception as exc:
        _fail(job_id, document_id, exc)
        raise
    _set(job_id, result=f"chunked: {n} chunks")
    return job_id


@celery.task(name="ingest.extract")
def task_extract(prev: object, job_id: str, document_id: str) -> str:
    from app.claims.service import extract_stage

    _set(job_id, stage="extract")
    try:
        n = extract_stage(document_id)
    except Exception as exc:
        _fail(job_id, document_id, exc)
        raise
    _set(job_id, result=f"extracted: {n} claims")
    return job_id


@celery.task(name="ingest.embed")
def task_embed(prev: object, job_id: str, document_id: str) -> str:
    from app.retrieval.service import embed_stage

    _set(job_id, stage="embed")
    try:
        n = embed_stage(document_id)
    except Exception as exc:
        _fail(job_id, document_id, exc)
        raise
    _set(job_id, result=f"embedded: {n} chunks")
    return job_id


@celery.task(name="ingest.finalize")
def ingest_finalize(prev: object, job_id: str, document_id: str) -> str:
    _set(job_id, status="done", stage="done")
    _set_document(document_id, status="done")
    log.info("ingest.done", job_id=job_id, document_id=document_id)
    return job_id


def _set_document(document_id: str, **fields: object) -> None:
    from app.db_models import Document

    with session_scope() as s:
        doc = s.get(Document, document_id)
        if doc is None:
            raise ValueError(f"document {document_id} not found")
        for key, value in fields.items():
            setattr(doc, key, value)


def start_ingestion(job_id: str, document_id: str) -> str:
    """Enqueue the real PDF ingestion chain. Returns the Celery result id."""
    workflow = chain(
        task_parse.si(job_id, document_id),
        task_chunk.s(job_id, document_id),
        task_extract.s(job_id, document_id),
        task_embed.s(job_id, document_id),
        ingest_finalize.s(job_id, document_id),
    )
    return workflow.apply_async().id


@celery.task(name="generate.output")
def task_generate(job_id: str, document_id: str, output_type: str, language: str) -> str:
    from app.generation.service import generate_output

    _set(job_id, status="processing", stage="generate")
    try:
        output_id = generate_output(document_id, output_type, language)
    except Exception as exc:
        _set(job_id, status="failed", error=str(exc))
        raise
    _set(job_id, status="done", stage="done", result=output_id)
    return job_id


def start_generation(job_id: str, document_id: str, output_type: str, language: str) -> str:
    """Enqueue a single generation task. Job.result holds the output id when done."""
    return task_generate.si(job_id, document_id, output_type, language).apply_async().id
