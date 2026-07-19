"""Retrieval tests using the deterministic hashing embedder + in-memory store."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.retrieval.embedder import HashingEmbedder
from app.retrieval.memory_store import InMemoryVectorStore
from tests.test_ingestion import make_pdf


def test_hashing_embedder_deterministic() -> None:
    e = HashingEmbedder(dim=64)
    a = e.embed_query("cervical cancer screening")
    b = e.embed_query("cervical cancer screening")
    assert a == b
    assert len(a) == 64


def test_in_memory_store_ranks_by_similarity() -> None:
    e = HashingEmbedder(dim=128)
    store = InMemoryVectorStore()
    docs = {
        "c1": "The screening system detects cervical cancer in Pap smears.",
        "c2": "The weather in Debrecen is pleasant during summer months.",
    }
    ids = list(docs)
    store.add(
        ids,
        e.embed_passages(list(docs.values())),
        list(docs.values()),
        [{"document_id": "d1"}, {"document_id": "d1"}],
    )

    hits = store.query(e.embed_query("cancer screening"), k=2, where={"document_id": "d1"})
    assert hits[0].id == "c1"  # the on-topic chunk ranks first
    # metadata filter excludes other documents
    assert store.query(e.embed_query("cancer"), k=2, where={"document_id": "other"}) == []


def test_search_endpoint(client: TestClient) -> None:
    body = (
        "1. Introduction\n\n"
        "We propose a screening method that achieved 88.8% accuracy on cervical cancer smears. "
        "However, the method is limited to born-digital images."
    )
    up = client.post("/documents", files={"file": ("p.pdf", make_pdf([body]), "application/pdf")})
    doc_id = up.json()["id"]

    r = client.post(
        f"/documents/{doc_id}/search", json={"query": "accuracy on cancer smears", "k": 3}
    )
    assert r.status_code == 200, r.text
    hits = r.json()
    assert hits, "expected at least one hit"
    assert any("88.8%" in h["text"] for h in hits)
    assert {"chunk_id", "page", "score", "text"} <= hits[0].keys()


def test_search_missing_document(client: TestClient) -> None:
    assert client.post("/documents/nope/search", json={"query": "x"}).status_code == 404
