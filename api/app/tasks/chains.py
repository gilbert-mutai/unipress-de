"""Demo pipeline: a Celery chain that walks a Job through stages in Postgres.

This is the Phase 0 stand-in for the real pipeline
(ingest -> parse -> claim-extract -> embed -> verify). It proves the full path:
api enqueues -> worker executes a chain -> each stage persists state -> api/UI read it.
"""

from __future__ import annotations

import time

from celery import chain

from app.core.db import session_scope
from app.core.logging import get_logger
from app.db_models import Job
from app.tasks.celery_app import celery

log = get_logger("tasks")

# Stand-in for the real pipeline stages; deepened in Phase 1+.
STAGES = ["ingest", "parse", "embed", "verify"]


def _set(job_id: str, **fields: object) -> None:
    with session_scope() as s:
        job = s.get(Job, job_id)
        if job is None:
            raise ValueError(f"job {job_id} not found")
        for key, value in fields.items():
            setattr(job, key, value)


@celery.task(name="pipeline.stage")
def run_stage(prev: object, job_id: str, stage: str) -> str:
    """Advance one stage. `prev` is the previous task's return (chain plumbing)."""
    log.info("stage.start", job_id=job_id, stage=stage)
    _set(job_id, status="processing", stage=stage)
    time.sleep(0.3)  # simulate work; replaced by real stage logic later
    return job_id


@celery.task(name="pipeline.finalize")
def finalize(prev: object, job_id: str) -> str:
    _set(
        job_id,
        status="done",
        stage="done",
        result=f"processed {len(STAGES)} stages: {', '.join(STAGES)}",
    )
    log.info("pipeline.done", job_id=job_id)
    return job_id


def start_pipeline(job_id: str) -> str:
    """Build and enqueue the demo stage chain (no document). Returns the result id."""
    # First stage is immutable (.si) so nothing is passed into it; the rest
    # receive the previous stage's return as their `prev` arg.
    steps = [run_stage.si(None, job_id, STAGES[0])]
    steps += [run_stage.s(job_id, stage) for stage in STAGES[1:]]
    steps.append(finalize.s(job_id))
    async_result = chain(*steps).apply_async()
    return async_result.id


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
