"""API tests for the document upload + ingestion flow (pipeline runs inline in tests)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_ingestion import KNOWN_SENTENCE, make_pdf


def test_upload_ingests_and_produces_chunks(client: TestClient) -> None:
    data = make_pdf(["1. Introduction\n\n" + KNOWN_SENTENCE, "2. Methods\n\nSecond page text."])
    r = client.post(
        "/documents",
        files={"file": ("paper.pdf", data, "application/pdf")},
    )
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["status"] == "done"
    assert doc["page_count"] == 2
    assert doc["chunk_count"] and doc["chunk_count"] > 0

    got = client.get(f"/documents/{doc['id']}")
    assert got.status_code == 200
    assert got.json()["chunk_count"] == doc["chunk_count"]

    chunks = client.get(f"/documents/{doc['id']}/chunks").json()
    assert len(chunks) == doc["chunk_count"]
    first = chunks[0]
    assert {"index", "page", "char_start", "char_end", "text"} <= first.keys()
    assert any(KNOWN_SENTENCE in c["text"] for c in chunks)


def test_upload_rejects_non_pdf(client: TestClient) -> None:
    r = client.post("/documents", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_get_missing_document(client: TestClient) -> None:
    assert client.get("/documents/nope").status_code == 404
