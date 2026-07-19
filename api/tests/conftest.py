"""Test fixtures: an in-process SQLite DB + tmp storage so tests need no infra."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> TestClient:
    # Build an isolated in-memory SQLite engine and point the app's session at it.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    from app.core import db
    from app.core.settings import get_settings
    from app.db_models import Claim, Document, Job  # noqa: F401 - ensure tables register

    db.Base.metadata.create_all(engine)
    monkeypatch.setattr(db, "SessionLocal", TestingSession)
    monkeypatch.setattr(db, "_engine", engine)

    # Route blob storage to a temp dir (used by both the upload route and the
    # inline ingestion below, so they share the same filesystem).
    settings = get_settings()
    settings.storage_root = str(tmp_path / "storage")
    # Retrieval with no downloads/services: deterministic embedder + in-memory store.
    settings.embed_backend = "hashing"
    settings.vector_backend = "memory"
    from app.retrieval import embedder as _emb
    from app.retrieval import service as _rsvc

    _emb.reset_embedder()
    _rsvc.reset_vector_store()

    from app.adapters import stubs

    # Demo /jobs pipeline: mark done inline.
    def _fake_pipeline(self: object, job_id: str) -> str:
        with db.session_scope() as s:
            job = s.get(Job, job_id)
            if job is not None:
                job.status, job.stage, job.result = "done", "done", "processed (test)"
        return "test-task-id"

    # Real ingestion pipeline: run parse + chunk inline (no Celery/Redis).
    def _fake_ingest(self: object, job_id: str, document_id: str) -> str:
        from app.claims.service import extract_stage
        from app.ingestion.service import chunk_stage, parse_stage
        from app.retrieval.service import embed_stage

        parse_stage(document_id)
        chunk_stage(document_id)
        extract_stage(document_id)
        embed_stage(document_id)
        with db.session_scope() as s:
            job = s.get(Job, job_id)
            if job is not None:
                job.status, job.stage = "done", "done"
            doc = s.get(Document, document_id)
            if doc is not None:
                doc.status = "done"
        return "test-ingest-id"

    monkeypatch.setattr(stubs.CeleryTaskDispatch, "enqueue_pipeline", _fake_pipeline)
    monkeypatch.setattr(stubs.CeleryTaskDispatch, "enqueue_ingestion", _fake_ingest)

    from app.main import app

    return TestClient(app)
