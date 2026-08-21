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


def test_review_decision_persists_and_shapes_the_publish_render(client: TestClient) -> None:
    """A flagged sentence must not reach the deliverable, and an edit must replace it."""
    from tests.test_ingestion import make_pdf

    paper = (
        "1. Introduction\n\n"
        "We propose a novel screening method for cervical cancer detection. "
        "The system achieved 88.8% accuracy across 339 smears. "
        "However, the approach is limited to born-digital images."
    )
    doc_id = client.post(
        "/documents", files={"file": ("p.pdf", make_pdf([paper]), "application/pdf")}
    ).json()["id"]
    output_id = client.post(
        f"/documents/{doc_id}/outputs", json={"output_type": "PRESS_RELEASE", "language": "en"}
    ).json()["result"]

    detail = client.get(f"/documents/outputs/{output_id}").json()
    sentences = detail["sentences"]
    assert all(s["decision"] is None for s in sentences), "nothing is decided yet"

    # Avoid a sentence whose text is also the headline: the fallback generator
    # lifts its title from a claim, so such a match would prove nothing.
    victim = next(s for s in sentences if s["text"] not in detail["title"])
    kept = next(s for s in reversed(sentences) if s["order_index"] != victim["order_index"])

    # Flag the first, rewrite the last.
    r = client.patch(
        f"/documents/outputs/{output_id}/sentences/{victim['order_index']}",
        json={"decision": "flagged"},
    )
    assert r.status_code == 200 and r.json()["decision"] == "flagged"
    r = client.patch(
        f"/documents/outputs/{output_id}/sentences/{kept['order_index']}",
        json={"decision": "accepted", "edited_text": "A reviewer rewrote this line."},
    )
    assert r.status_code == 200 and r.json()["edited_text"] == "A reviewer rewrote this line."

    # Decisions survive a fresh read, they are on the row, not in a browser.
    reread = {
        s["order_index"]: s
        for s in client.get(f"/documents/outputs/{output_id}").json()["sentences"]
    }
    assert reread[victim["order_index"]]["decision"] == "flagged"
    assert reread[kept["order_index"]]["decision"] == "accepted"
    # The original text stays on record next to the rewrite.
    assert reread[kept["order_index"]]["text"] == kept["text"]

    publish = client.get(
        f"/documents/outputs/{output_id}/render", params={"format": "html", "view": "publish"}
    ).text
    assert victim["text"][:40] not in publish, "a flagged sentence reached the deliverable"
    assert "A reviewer rewrote this line." in publish
    # No verdict furniture in something meant for a newsroom.
    for noise in ("SUPPORTED", "UNSUPPORTED", "INTERPRETATION", "clm_"):
        assert noise not in publish, f"publish view leaked {noise}"

    # The evidence record still shows everything, including the flagged sentence.
    evidence = client.get(f"/documents/outputs/{output_id}/render", params={"format": "html"}).text
    assert victim["text"][:40] in evidence
    assert "clm_" in evidence


def test_review_rejects_unknown_sentence_and_bad_view(client: TestClient) -> None:
    from tests.test_ingestion import make_pdf

    doc_id = client.post(
        "/documents",
        files={
            "file": (
                "p.pdf",
                make_pdf(["1. Intro\n\nA claim of some length here."]),
                "application/pdf",
            )
        },
    ).json()["id"]
    output_id = client.post(
        f"/documents/{doc_id}/outputs", json={"output_type": "SOCIAL", "language": "en"}
    ).json()["result"]

    assert (
        client.patch(
            f"/documents/outputs/{output_id}/sentences/999", json={"decision": "flagged"}
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/documents/outputs/{output_id}/sentences/0", json={"decision": "maybe"}
        ).status_code
        == 422
    )
    assert (
        client.get(
            f"/documents/outputs/{output_id}/render", params={"view": "sideways"}
        ).status_code
        == 400
    )


def test_clear_reviews_restores_the_full_deliverable(client: TestClient) -> None:
    """A rehearsal leaves flags behind; clearing must bring the whole text back."""
    from tests.test_ingestion import make_pdf

    paper = (
        "1. Introduction\n\n"
        "We propose a novel screening method for cervical cancer detection. "
        "The system achieved 88.8% accuracy across 339 smears. "
        "However, the approach is limited to born-digital images."
    )
    doc_id = client.post(
        "/documents", files={"file": ("p.pdf", make_pdf([paper]), "application/pdf")}
    ).json()["id"]
    output_id = client.post(
        f"/documents/{doc_id}/outputs", json={"output_type": "PRESS_RELEASE", "language": "en"}
    ).json()["result"]

    full = client.get(
        f"/documents/outputs/{output_id}/render", params={"view": "publish"}
    ).text.count("<p>")

    sentences = client.get(f"/documents/outputs/{output_id}").json()["sentences"]
    client.patch(
        f"/documents/outputs/{output_id}/sentences/{sentences[1]['order_index']}",
        json={"decision": "flagged"},
    )
    client.patch(
        f"/documents/outputs/{output_id}/sentences/{sentences[0]['order_index']}",
        json={"decision": "accepted", "edited_text": "A rewritten opening."},
    )
    shortened = client.get(
        f"/documents/outputs/{output_id}/render", params={"view": "publish"}
    ).text
    assert shortened.count("<p>") == full - 1
    assert "A rewritten opening." in shortened

    cleared = client.delete(f"/documents/outputs/{output_id}/reviews")
    assert cleared.status_code == 200
    assert all(s["decision"] is None for s in cleared.json()["sentences"])
    assert all(s["edited_text"] is None for s in cleared.json()["sentences"])

    restored = client.get(f"/documents/outputs/{output_id}/render", params={"view": "publish"}).text
    assert restored.count("<p>") == full, "clearing did not restore every sentence"
    assert "A rewritten opening." not in restored, "the edit outlived the reset"

    # Idempotent, and unknown outputs 404 rather than silently succeeding.
    assert client.delete(f"/documents/outputs/{output_id}/reviews").status_code == 200
    assert client.delete("/documents/outputs/nope/reviews").status_code == 404


def test_footer_is_a_readable_citation_not_a_dict(client: TestClient) -> None:
    """The publish footer printed the raw mapping, which read as a JSON blob."""
    from tests.test_ingestion import make_pdf

    doc_id = client.post(
        "/documents",
        files={
            "file": (
                "p.pdf",
                make_pdf(["1. Intro\n\nA claim with enough words to survive."]),
                "application/pdf",
            )
        },
    ).json()["id"]
    output_id = client.post(
        f"/documents/{doc_id}/outputs", json={"output_type": "PRESS_RELEASE", "language": "en"}
    ).json()["result"]

    for view in ("publish", "evidence"):
        html = client.get(f"/documents/outputs/{output_id}/render", params={"view": view}).text
        assert "Source:" in html, f"{view} lost its source line"
        # A Python mapping leaks these; a citation line has none of them.
        for tell in ("{'title'", "'authors':", "'doi':", "['"):
            assert tell not in html, f"{view} footer rendered a raw dict: {tell}"
        assert "text-align: justify" in html, f"{view} prose is not justified"


def test_citation_line_orders_the_fields(monkeypatch) -> None:
    from app.outputs import manifest

    monkeypatch.setattr(
        manifest,
        "_load_manifest",
        lambda _p: {
            "p.pdf": {
                "file": "p.pdf",
                "title": "A Title With A Trailing Stop.",
                "authors": ["A Author", "B Author"],
                "venue": "A Journal 1:2 (2026)",
                "doi": "10.0000/x",
                "license": "CC BY 4.0",
            }
        },
    )
    line = manifest.citation_for("p.pdf")
    assert line == (
        "A Author, B Author. A Title With A Trailing Stop. A Journal 1:2 (2026). "
        "DOI: 10.0000/x. Licence: CC BY 4.0."
    ), line
    # An unknown file degrades to the filename rather than failing a render.
    assert manifest.citation_for("missing.pdf") == "missing.pdf."


def test_evidence_record_keeps_the_generated_text_beside_an_edit(client: TestClient) -> None:
    """The audit trail is the contrast: what the model wrote, and what went out."""
    from tests.test_ingestion import make_pdf

    paper = (
        "1. Introduction\n\n"
        "We propose a novel screening method for cervical cancer detection. "
        "The system achieved 88.8% accuracy across 339 smears."
    )
    doc_id = client.post(
        "/documents", files={"file": ("p.pdf", make_pdf([paper]), "application/pdf")}
    ).json()["id"]
    output_id = client.post(
        f"/documents/{doc_id}/outputs", json={"output_type": "PRESS_RELEASE", "language": "en"}
    ).json()["result"]

    sentences = client.get(f"/documents/outputs/{output_id}").json()["sentences"]
    target = sentences[1]
    replacement = "A reviewer rewrote this line with care."
    client.patch(
        f"/documents/outputs/{output_id}/sentences/{target['order_index']}",
        json={"edited_text": replacement},
    )

    evidence = client.get(
        f"/documents/outputs/{output_id}/render", params={"view": "evidence"}
    ).text
    assert replacement in evidence, "the reviewer's wording should lead"
    assert target["text"][:40] in evidence, "the generated original must remain on the record"
    assert "edited" in evidence

    publish = client.get(f"/documents/outputs/{output_id}/render", params={"view": "publish"}).text
    assert replacement in publish
    assert target["text"][:40] not in publish, "publish must not carry the superseded wording"


def test_reverting_an_edit_restores_the_generated_wording(client: TestClient) -> None:
    from tests.test_ingestion import make_pdf

    doc_id = client.post(
        "/documents",
        files={
            "file": (
                "p.pdf",
                make_pdf(
                    [
                        "1. Introduction\n\n"
                        "We propose a novel screening method for cervical cancer detection. "
                        "The system achieved 88.8% accuracy across 339 smears."
                    ]
                ),
                "application/pdf",
            )
        },
    ).json()["id"]
    output_id = client.post(
        f"/documents/{doc_id}/outputs", json={"output_type": "SOCIAL", "language": "en"}
    ).json()["result"]
    idx = client.get(f"/documents/outputs/{output_id}").json()["sentences"][0]["order_index"]

    client.patch(
        f"/documents/outputs/{output_id}/sentences/{idx}", json={"edited_text": "Rewritten."}
    )
    # An empty string means "no edit", not "publish an empty sentence".
    r = client.patch(f"/documents/outputs/{output_id}/sentences/{idx}", json={"edited_text": "  "})
    assert r.status_code == 200
    assert r.json()["edited_text"] is None
    publish = client.get(f"/documents/outputs/{output_id}/render", params={"view": "publish"}).text
    assert "Rewritten." not in publish
