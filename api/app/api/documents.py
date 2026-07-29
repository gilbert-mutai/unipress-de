"""Documents API: upload a PDF, then read ingestion status and resulting chunks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
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

# Ingestion stage → rough completion percentage (for the UI progress bar).
_STAGE_PROGRESS = {"queued": 5, "parse": 25, "chunk": 45, "extract": 65, "embed": 85, "done": 100}


def _with_progress(doc: Document, db: Session) -> DocumentRead:
    """Build a DocumentRead with the latest ingestion stage + a 0–100 progress."""
    job = db.scalars(
        select(Job).where(Job.document_id == doc.id).order_by(Job.created_at.desc())
    ).first()
    stage = job.stage if job else None
    if doc.status == "done":
        progress = 100
    elif doc.status == "failed":
        progress = _STAGE_PROGRESS.get(stage or "", 0)
    else:
        progress = _STAGE_PROGRESS.get(stage or "queued", 5)
    return DocumentRead.model_validate(doc).model_copy(
        update={"stage": stage, "progress": progress}
    )


@router.post("", response_model=DocumentRead, status_code=201)
async def upload_document(
    file: UploadFile,
    db: Session = Depends(get_db),
    storage: Storage = Depends(get_storage),
) -> DocumentRead:
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
    return _with_progress(doc, db)


@router.get("/{document_id}", response_model=DocumentRead)
def get_document(document_id: str, db: Session = Depends(get_db)) -> DocumentRead:
    doc = db.get(Document, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    return _with_progress(doc, db)


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


@router.get("/{document_id}/pages/{page}.png")
def get_page_image(
    document_id: str, page: int, bbox: str | None = None, db: Session = Depends(get_db)
) -> Response:
    """Render a source PDF page as PNG, optionally highlighting a cited span (x0,y0,x1,y1)."""
    if db.get(Document, document_id) is None:
        raise HTTPException(status_code=404, detail="document not found")
    box: list[float] | None = None
    if bbox:
        try:
            box = [float(v) for v in bbox.split(",")]
            if len(box) != 4:
                raise ValueError
        except ValueError:
            raise HTTPException(status_code=400, detail="bbox must be 'x0,y0,x1,y1'") from None

    from app.ingestion.pageimage import render_page_png

    try:
        png = render_page_png(document_id, page, box)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return Response(content=png, media_type="image/png", headers={"Cache-Control": "max-age=3600"})


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

    # Demo safety (docs/08 P6): an output already generated for this
    # (document, type, language) is returned as an already-complete job, so the
    # UI resolves it in one round trip with no model call. That removes live
    # rate-limit and latency risk from the demo path — the durable outputs table
    # *is* the cache, rather than a second copy in Redis that can disagree with
    # it. `refresh=true` forces a fresh generation.
    if not payload.refresh:
        existing = db.scalars(
            select(OutputRecord)
            .where(
                OutputRecord.document_id == document_id,
                OutputRecord.output_type == payload.output_type,
                OutputRecord.language == payload.language,
                OutputRecord.status == "done",
            )
            .order_by(OutputRecord.created_at.desc())
            .limit(1)
        ).first()
        if existing is not None:
            job = Job(
                document_id=document_id,
                status="done",
                stage="cached",
                result=existing.id,
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            return job

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


@router.get("/outputs/{output_id}/render")
def render_output(output_id: str, format: str = "html", db: Session = Depends(get_db)) -> Response:
    """Render an output as HTML (default) or PDF, with evidence trail + attribution."""
    output = db.get(OutputRecord, output_id)
    if output is None:
        raise HTTPException(status_code=404, detail="output not found")
    doc = db.get(Document, output.document_id)
    source_filename = doc.filename if doc else output.title

    from app.outputs.render import render_html

    if format == "html":
        return HTMLResponse(content=render_html(output, source_filename))
    if format == "pdf":
        try:
            from app.outputs.render import render_pdf

            pdf = render_pdf(output, source_filename)
        except (ImportError, OSError) as exc:  # WeasyPrint system libs missing
            raise HTTPException(
                status_code=501, detail=f"PDF rendering unavailable: {exc}"
            ) from exc
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{output_id}.pdf"'},
        )
    raise HTTPException(status_code=400, detail="format must be 'html' or 'pdf'")
