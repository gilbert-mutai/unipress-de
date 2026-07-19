"""Tests for the quote-verification guardrail and the heuristic claim extractor."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.claims.guardrail import find_span, normalize_ws
from app.claims.heuristic import extract_claims
from app.ingestion.models import Chunk, SourceSpan
from tests.test_ingestion import make_pdf


def _chunk(text: str, doc_id: str = "d1", page: int = 1, start: int = 0) -> Chunk:
    return Chunk(
        index=0,
        text=text,
        span=SourceSpan(
            doc_id=doc_id,
            page=page,
            section=None,
            char_start=start,
            char_end=start + len(text),
            quote=text,
            bbox=[0, 0, 1, 1],
        ),
    )


def test_guardrail_finds_exact_and_whitespace_flexible() -> None:
    src = "The method reached 88.8% accuracy on the test set."
    assert find_span(src, "88.8% accuracy") == (19, 33)
    # whitespace differences (newline vs space) still match
    assert find_span("The method\nreached 88.8%", "method reached 88.8%") is not None


def test_guardrail_rejects_absent_quote() -> None:
    # A hallucinated quote not present in the source must be rejected (None).
    assert find_span("Accuracy was 88.8 percent.", "accuracy was 98.8 percent") is None
    assert normalize_ws("a\n  b\t c") == "a b c"


def test_heuristic_extracts_quote_verified_claims() -> None:
    text = (
        "We propose a novel screening method for cervical cancer detection. "
        "The system achieved 88.8% accuracy across 339 smears. "
        "However, the approach is limited to born-digital images. "
        "The weather in Debrecen is pleasant in summer."  # non-claim filler
    )
    claims = extract_claims([_chunk(text)])
    assert claims, "expected claims"

    # Provenance: every claim's quote is a verbatim substring at its offsets.
    for c in claims:
        assert text[c.span.char_start : c.span.char_end] == c.span.quote
        assert c.key.startswith("clm_")

    types = {c.claim_type.value for c in claims}
    assert "QUANTITATIVE" in types
    assert "LIMITATION" in types
    # A numeric claim is flagged.
    assert any(c.numeric for c in claims)


def test_claims_endpoint(client: TestClient) -> None:
    body = (
        "1. Introduction\n\n"
        "We propose a new method that achieved 88.8% accuracy on 339 samples. "
        "However, the method is limited to English text."
    )
    r = client.post("/documents", files={"file": ("p.pdf", make_pdf([body]), "application/pdf")})
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["claim_count"] and doc["claim_count"] > 0

    claims = client.get(f"/documents/{doc['id']}/claims").json()
    assert len(claims) == doc["claim_count"]
    assert {"key", "text", "claim_type", "quote", "page", "numeric"} <= claims[0].keys()
