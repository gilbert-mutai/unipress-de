"""Jobs API: the thin enqueue + read surface (all heavy work lives in the worker)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.adapters.stubs import CeleryTaskDispatch
from app.core.db import get_db
from app.db_models import Job
from app.models import JobCreate, JobRead

router = APIRouter(prefix="/jobs", tags=["jobs"])

_dispatch = CeleryTaskDispatch()


@router.post("", response_model=JobRead, status_code=201)
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> Job:
    """Create a job row and enqueue the pipeline. Returns immediately."""
    job = Job(input_text=payload.input_text, status="pending", stage="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    _dispatch.enqueue_pipeline(job.id)
    return job


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: str, db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job
