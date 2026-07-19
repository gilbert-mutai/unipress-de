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
    """Build and enqueue the stage chain. Returns the Celery result id."""
    # First stage is immutable (.si) so nothing is passed into it; the rest
    # receive the previous stage's return as their `prev` arg.
    steps = [run_stage.si(None, job_id, STAGES[0])]
    steps += [run_stage.s(job_id, stage) for stage in STAGES[1:]]
    steps.append(finalize.s(job_id))
    async_result = chain(*steps).apply_async()
    return async_result.id
