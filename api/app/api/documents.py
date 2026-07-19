"""Documents API: upload a PDF, then read ingestion status and resulting chunks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.stubs import CeleryTaskDispatch
from app.core.db import get_db
from app.db_models import Chunk, Claim, Document, Job
from app.models import ChunkRead, ClaimRead, DocumentRead
from app.ports import Storage

from .deps import get_storage

router = APIRouter(prefix="/documents", tags=["documents"])

_MAX_BYTES = 30 * 1024 * 1024  # 30 MB upload cap
_dispatch = CeleryTaskDispatch()


@router.post("", response_model=DocumentRead, status_code=201)
async def upload_document(
    file: UploadFile,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage),
) -> Document:
    """Store an uploaded PDF and enqueue the ingestion pipeline."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="only .pdf uploads are supported")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="empty file")
    if len(data) > _MAX_BYTES:
        raise HTTPException(status_code=413, detail="file too large")

    doc = Document(filename=file.filename or "upload.pdf", content_key="", status="pending")
    db.add(doc)
    db.commit()
    db.refresh(doc)

    key = f"{doc.id}/source.pdf"
    storage.put(key, data)
    doc.content_key = key
    db.commit()

    job = Job(document_id=doc.id, status="pending", stage="queued")
    db.add(job)
    db.commit()

    _dispatch.enqueue_ingestion(job.id, doc.id)
    db.refresh(doc)
    return doc


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, db: Session = Depends(get_db)) -> Document:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    return doc


@router.get("/{document_id}/chunks", response_model=list[ChunkRead])
def get_chunks(document_id: str, db: Session = Depends(get_db)) -> list[Chunk]:
    if db.get(Document, document_id) is None:
        raise HTTPException(status_code=404, detail="document not found")
    return list(
        db.scalars(select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.index))
    )


@router.get("/{document_id}/claims", response_model=list[ClaimRead])
def get_claims(document_id: str, db: Session = Depends(get_db)) -> list[Claim]:
    if db.get(Document, document_id) is None:
        raise HTTPException(status_code=404, detail="document not found")
    return list(
        db.scalars(select(Claim).where(Claim.document_id == document_id).order_by(Claim.key))
    )
