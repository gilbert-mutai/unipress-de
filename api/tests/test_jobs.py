from fastapi.testclient import TestClient


def test_read_job(client: TestClient) -> None:
    """Jobs are created by the pipelines that own them, then polled here."""
    from app.core import db
    from app.db_models import Job

    with db.session_scope() as s:
        job = Job(status="processing", stage="parse")
        s.add(job)
        s.flush()
        job_id = job.id

    r = client.get(f"/jobs/{job_id}")
    assert r.status_code == 200
    assert r.json()["stage"] == "parse"
    assert r.json()["status"] == "processing"


def test_no_public_job_create_route(client: TestClient) -> None:
    """POST /jobs was the Phase 0 skeleton's arbitrary-text enqueue; it is gone.

    404 rather than 405: with the create route removed nothing is mounted at
    /jobs at all, only /jobs/{job_id}.
    """
    r = client.post("/jobs", json={"input_text": "a paper"})
    assert r.status_code == 404


def test_get_missing_job(client: TestClient) -> None:
    r = client.get("/jobs/does-not-exist")
    assert r.status_code == 404


def test_ports_satisfied_by_adapters() -> None:
    from app.adapters.stubs import EchoLLM, LocalStorage
    from app.ports import LLMGateway, Storage, VectorStore
    from app.retrieval.memory_store import InMemoryVectorStore

    assert isinstance(InMemoryVectorStore(), VectorStore)
    assert isinstance(EchoLLM(), LLMGateway)
    assert isinstance(LocalStorage("/tmp/unipress-test-storage"), Storage)
