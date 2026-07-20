"""Documents API: upload a PDF, then read ingestion status and resulting chunks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.stubs import CeleryTaskDispatch
from app.core.db import get_db
from app.db_models import Chunk, Claim, Document, Job, OutputRecord
from app.models import (
    ChunkRead,
    ClaimRead,
    DocumentRead,
    GenerateRequest,
    JobRead,
    OutputDetail,
    OutputSummary,
    SearchHit,
    SearchQuery,
)
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


@router.post("/{document_id}/search", response_model=list[SearchHit])
def search_document(
    document_id: str, payload: SearchQuery, db: Session = Depends(get_db)
) -> list[SearchHit]:
    """Semantic search over a document's embedded chunks (the RAG retrieval step)."""
    if db.get(Document, document_id) is None:
        raise HTTPException(status_code=404, detail="document not found")

    from app.retrieval.service import search

    hits = search(document_id, payload.query, payload.k)
    return [
        SearchHit(
            chunk_id=h.id,
            page=int(h.metadata.get("page", 0)),
            section=h.metadata.get("section"),
            char_start=h.metadata.get("char_start"),
            char_end=h.metadata.get("char_end"),
            score=round(1.0 - h.distance, 4),
            text=h.text,
        )
        for h in hits
    ]


@router.post("/{document_id}/outputs", response_model=JobRead, status_code=202)
def generate_output(
    document_id: str, payload: GenerateRequest, db: Session = Depends(get_db)
) -> Job:
    """Enqueue claim-bound generation of one output (poll the job; result = output id)."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    if doc.status != "done":
        raise HTTPException(status_code=409, detail="document ingestion not complete")

    from app.generation.models import OutputType
    from app.generation.specs import SPECS

    try:
        if OutputType(payload.output_type) not in SPECS:
            raise ValueError
    except ValueError:
        raise HTTPException(
            status_code=400, detail=f"unsupported output_type: {payload.output_type}"
        ) from None

    job = Job(document_id=document_id, status="pending", stage="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    _dispatch.enqueue_generation(job.id, document_id, payload.output_type, payload.language)
    db.refresh(job)
    return job


@router.get("/{document_id}/outputs", response_model=list[OutputSummary])
def list_outputs(document_id: str, db: Session = Depends(get_db)) -> list[OutputRecord]:
    if db.get(Document, document_id) is None:
        raise HTTPException(status_code=404, detail="document not found")
    return list(
        db.scalars(
            select(OutputRecord)
            .where(OutputRecord.document_id == document_id)
            .order_by(OutputRecord.created_at)
        )
    )


@router.get("/outputs/{output_id}", response_model=OutputDetail)
def get_output(output_id: str, db: Session = Depends(get_db)) -> OutputRecord:
    output = db.get(OutputRecord, output_id)
    if output is None:
        raise HTTPException(status_code=404, detail="output not found")
    return output
