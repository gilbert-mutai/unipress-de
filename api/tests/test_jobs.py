from fastapi.testclient import TestClient


def test_create_and_read_job(client: TestClient) -> None:
    r = client.post("/jobs", json={"input_text": "a paper"})
    assert r.status_code == 201
    job = r.json()
    assert job["id"]
    assert job["input_text"] == "a paper"

    # The stubbed dispatch runs the pipeline inline, so it's already done.
    got = client.get(f"/jobs/{job['id']}")
    assert got.status_code == 200
    assert got.json()["status"] == "done"


def test_get_missing_job(client: TestClient) -> None:
    r = client.get("/jobs/does-not-exist")
    assert r.status_code == 404


def test_ports_satisfied_by_stubs() -> None:
    from app.adapters.stubs import EchoLLM, InMemoryVectorStore, LocalStorage
    from app.ports import LLMGateway, Storage, VectorStore

    assert isinstance(InMemoryVectorStore(), VectorStore)
    assert isinstance(EchoLLM(), LLMGateway)
    assert isinstance(LocalStorage("/tmp/unipress-test-storage"), Storage)
