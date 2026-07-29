import pytest
from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ready(client: TestClient) -> None:
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json()["status"] == "ready"


def test_ready_reports_503_when_the_db_is_unreachable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A monitor reading only the status code must still see the outage."""
    from app.api import health

    def boom() -> None:
        raise RuntimeError("connection refused")

    monkeypatch.setattr(health, "get_engine", boom)
    r = client.get("/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "not-ready"
    assert "connection refused" in r.json()["db"]


def test_root(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["service"] == "unipress-de"
