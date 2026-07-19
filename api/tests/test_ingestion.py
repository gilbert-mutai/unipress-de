"""Unit tests for the parser + chunker, using a PDF generated in-memory (no fixtures)."""

from __future__ import annotations

import fitz  # PyMuPDF

from app.ingestion.chunker import chunk_document
from app.ingestion.parser import parse_pdf

KNOWN_SENTENCE = "The proposed method reached 88.8% accuracy on the test set."


def make_pdf(pages: list[str]) -> bytes:
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        page.insert_textbox(fitz.Rect(72, 72, 520, 760), text, fontsize=11)
    return doc.tobytes()


def test_parse_reports_pages_and_text() -> None:
    data = make_pdf(["1. Introduction\n\n" + KNOWN_SENTENCE, "2. Methods\n\nA second page."])
    parsed = parse_pdf(data, doc_id="d1", filename="t.pdf")
    assert parsed.page_count == 2
    assert "88.8%" in parsed.full_text
    assert all(len(b.bbox) == 4 for p in parsed.pages for b in p.blocks)


def test_chunk_provenance_integrity() -> None:
    data = make_pdf(["1. Introduction\n\n" + KNOWN_SENTENCE])
    parsed = parse_pdf(data, doc_id="d1", filename="t.pdf")
    chunks = chunk_document(parsed)
    assert chunks, "expected at least one chunk"

    page_text = {p.number: p.text for p in parsed.pages}
    for c in chunks:
        # The core guarantee: quote is a verbatim substring at the recorded offsets.
        assert page_text[c.span.page][c.span.char_start : c.span.char_end] == c.span.quote
        assert c.span.doc_id == "d1"

    assert any(KNOWN_SENTENCE in c.text for c in chunks)


def test_image_only_page_flagged() -> None:
    # A page with no text blocks but an image => flagged as image-only.
    doc = fitz.open()
    page = doc.new_page()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10))
    page.insert_image(fitz.Rect(72, 72, 200, 200), pixmap=pix)
    parsed = parse_pdf(doc.tobytes(), doc_id="img", filename="scan.pdf")
    assert parsed.pages[0].image_only is True
    assert parsed.warnings
