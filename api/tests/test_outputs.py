"""Rendering tests: HTML structure, evidence trail, attribution, all output specs."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.generation.models import OutputType
from app.generation.specs import SPECS
from tests.test_ingestion import make_pdf

PAPER = (
    "1. Introduction\n\n"
    "We propose a screening method that achieved 88.8% accuracy across 339 smears. "
    "However, the approach is limited to born-digital images."
)


def test_all_five_output_types_have_specs() -> None:
    assert set(SPECS) == {
        OutputType.PRESS_RELEASE,
        OutputType.ARTICLE,
        OutputType.SOCIAL,
        OutputType.EXEC_SUMMARY,
        OutputType.VIDEO_SCRIPT,
    }


def _generate(client: TestClient, output_type: str) -> str:
    up = client.post("/documents", files={"file": ("p.pdf", make_pdf([PAPER]), "application/pdf")})
    doc_id = up.json()["id"]
    job = client.post(
        f"/documents/{doc_id}/outputs", json={"output_type": output_type, "language": "en"}
    )
    return job.json()["result"]


def test_render_html_has_evidence_trail_and_attribution(client: TestClient) -> None:
    output_id = _generate(client, "PRESS_RELEASE")
    r = client.get(f"/documents/outputs/{output_id}/render", params={"format": "html"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    html = r.text
    assert "<h1>" in html
    assert "clm_" in html  # claim citation in the evidence trail
    assert "SUPPORTED" in html  # verdict badge
    assert "Source:" in html  # attribution footer
    assert "UniPress DE" in html


def test_render_bad_format(client: TestClient) -> None:
    output_id = _generate(client, "EXEC_SUMMARY")
    assert (
        client.get(f"/documents/outputs/{output_id}/render", params={"format": "docx"}).status_code
        == 400
    )


def test_render_missing_output(client: TestClient) -> None:
    assert client.get("/documents/outputs/nope/render").status_code == 404
