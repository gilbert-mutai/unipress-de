"""Test fixtures: an in-process SQLite DB so unit tests need no Postgres."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Build an isolated in-memory SQLite engine and point the app's session at it.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    from app.core import db
    from app.db_models import Job  # noqa: F401 - ensure table is registered

    db.Base.metadata.create_all(engine)
    monkeypatch.setattr(db, "SessionLocal", TestingSession)
    monkeypatch.setattr(db, "_engine", engine)

    # Never hit Celery/Redis in unit tests: run the pipeline inline.
    from app.adapters import stubs

    def _fake_enqueue(self: object, job_id: str) -> str:
        with db.session_scope() as s:
            job = s.get(Job, job_id)
            if job is not None:
                job.status = "done"
                job.stage = "done"
                job.result = "processed (test)"
        return "test-task-id"

    monkeypatch.setattr(stubs.CeleryTaskDispatch, "enqueue_pipeline", _fake_enqueue)

    from app.main import app

    return TestClient(app)
