"""Jobs API: read-only progress for work enqueued elsewhere.

Jobs are created by the pipelines that own them — ingestion (POST /documents)
and generation (POST /documents/{id}/outputs). There is deliberately no public
create route: the Phase 0 skeleton had one taking arbitrary `input_text`, which
let anyone spend worker time on a job bound to no document.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.db_models import Job
from app.models import JobRead

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: str, db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job
