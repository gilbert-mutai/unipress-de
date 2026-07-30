"""Generation API tests (fallback generator + TrustLayer run inline in tests)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_ingestion import make_pdf

PAPER = (
    "1. Introduction\n\n"
    "We propose a novel screening method for cervical cancer detection. "
    "The system achieved 88.8% accuracy across 339 smears. "
    "However, the approach is limited to born-digital images."
)


def _ingest(client: TestClient) -> str:
    r = client.post("/documents", files={"file": ("p.pdf", make_pdf([PAPER]), "application/pdf")})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_generate_press_release_is_claim_bound_and_verified(client: TestClient) -> None:
    doc_id = _ingest(client)

    job = client.post(
        f"/documents/{doc_id}/outputs", json={"output_type": "PRESS_RELEASE", "language": "en"}
    )
    assert job.status_code == 202, job.text
    body = job.json()
    assert body["status"] == "done"  # inline in tests
    output_id = body["result"]

    detail = client.get(f"/documents/outputs/{output_id}").json()
    assert detail["output_type"] == "PRESS_RELEASE"
    assert detail["sentences"], "expected generated sentences"

    factual = [s for s in detail["sentences"] if s["role"] in ("FACT", "INTERPRETATION")]
    assert factual, "expected factual sentences"
    for s in factual:
        assert s["claim_ids"], "every factual sentence must cite a claim"
        assert s["verdict"] is not None
        assert s["confidence"] is not None
    # The fallback renders verified claims verbatim, so they should be SUPPORTED.
    assert any(s["verdict"] == "SUPPORTED" for s in factual)


def test_list_outputs_and_validation(client: TestClient) -> None:
    doc_id = _ingest(client)
    client.post(
        f"/documents/{doc_id}/outputs", json={"output_type": "EXEC_SUMMARY", "language": "en"}
    )

    outputs = client.get(f"/documents/{doc_id}/outputs").json()
    assert len(outputs) == 1
    assert outputs[0]["output_type"] == "EXEC_SUMMARY"

    bad = client.post(
        f"/documents/{doc_id}/outputs", json={"output_type": "HAIKU", "language": "en"}
    )
    assert bad.status_code == 400


def test_repeat_request_reuses_the_existing_output(client: TestClient) -> None:
    """Demo safety: a second request for the same (type, language) must not regenerate."""
    doc_id = _ingest(client)
    body = {"output_type": "PRESS_RELEASE", "language": "en"}

    first = client.post(f"/documents/{doc_id}/outputs", json=body).json()
    generated_id = first["result"]

    # Make a further generation impossible: if the endpoint were to enqueue
    # again, this would raise rather than quietly produce a second output.
    from app.adapters import stubs

    def _boom(*a: object, **k: object) -> str:
        raise AssertionError("regenerated instead of reusing the existing output")

    original = stubs.CeleryTaskDispatch.enqueue_generation
    stubs.CeleryTaskDispatch.enqueue_generation = _boom  # type: ignore[method-assign]
    try:
        second = client.post(f"/documents/{doc_id}/outputs", json=body).json()
    finally:
        stubs.CeleryTaskDispatch.enqueue_generation = original  # type: ignore[method-assign]

    assert second["status"] == "done"
    assert second["stage"] == "cached"
    assert second["result"] == generated_id

    # Still exactly one output for the document, not two.
    assert len(client.get(f"/documents/{doc_id}/outputs").json()) == 1

    # refresh=true bypasses the reuse and generates again.
    third = client.post(f"/documents/{doc_id}/outputs", json={**body, "refresh": True}).json()
    assert third["result"] != generated_id
    assert len(client.get(f"/documents/{doc_id}/outputs").json()) == 2


def test_video_script_has_timed_scenes(client: TestClient) -> None:
    doc_id = _ingest(client)
    job = client.post(
        f"/documents/{doc_id}/outputs", json={"output_type": "VIDEO_SCRIPT", "language": "en"}
    )
    output_id = job.json()["result"]
    detail = client.get(f"/documents/outputs/{output_id}").json()

    scenes = detail["sentences"]
    assert scenes, "expected video scenes"
    # Every scene carries a timecode + on-screen text; factual scenes cite claims.
    assert all(s["timecode"] for s in scenes)
    assert any(s["on_screen"] for s in scenes)
    assert any(s["section"] == "hook" for s in scenes)
    assert any(s["section"] == "cta" for s in scenes)

    # The rendered HTML is a scene table with the timecodes.
    html = client.get(f"/documents/outputs/{output_id}/render", params={"format": "html"}).text
    assert 'table class="scenes"' in html
    assert "0:00" in html


def test_generate_requires_ingested_document(client: TestClient) -> None:
    # A document id that doesn't exist => 404.
    assert (
        client.post("/documents/nope/outputs", json={"output_type": "PRESS_RELEASE"}).status_code
        == 404
    )


def test_inline_claim_citations_are_stripped_from_prose() -> None:
    """Claim ids belong in claim_ids, not in published text."""
    from app.generation.llm_generator import _strip_inline_citations

    assert _strip_inline_citations("It raises capacity (clm_003, clm_005).") == (
        "It raises capacity."
    )
    assert _strip_inline_citations("Ends here [CLM-12] .") == "Ends here."
    assert _strip_inline_citations("Nothing to strip here.") == "Nothing to strip here."
