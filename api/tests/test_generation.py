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
