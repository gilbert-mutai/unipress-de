"""Render a generated output to HTML (Jinja2) or PDF (WeasyPrint).

HTML is dependency-light and always available (the review UI and tests use it).
PDF is produced by WeasyPrint, imported lazily because it needs system libraries
(pango/cairo) present in the container; unavailable environments raise a clear error.
"""

from __future__ import annotations

from itertools import groupby
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.db_models import OutputRecord
from app.outputs.manifest import citation_for

_TEMPLATES = Path(__file__).parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES)),
    autoescape=select_autoescape(["html"]),
)


def _sections(record: OutputRecord) -> list[tuple[str | None, list]]:
    """Group sentences (already ordered) by their section slot, preserving order."""
    sentences = sorted(record.sentences, key=lambda s: s.order_index)
    grouped = groupby(sentences, key=lambda s: s.section)
    return [(section, list(group)) for section, group in grouped]


def _publishable(record: OutputRecord) -> list[Any]:
    """Sentences fit to publish: flagged ones dropped, edits substituted.

    The reviewer's ruling has to bite somewhere, and this is where. A sentence they
    struck must not reappear in the artefact they hand to a journalist, and a
    sentence they rewrote should appear as they wrote it.
    """
    # SentenceRecord rows and edited stand-ins mix here; the template only reads
    # attributes, so the shape is duck-typed rather than a shared class.
    kept: list[Any] = []
    for s in sorted(record.sentences, key=lambda s: s.order_index):
        if s.decision == "flagged":
            continue
        if s.edited_text:
            # A shallow stand-in so the template reads the rewrite without the
            # session tracking a mutation on the stored row.
            kept.append(
                SimpleNamespace(
                    **{
                        **{c.name: getattr(s, c.name) for c in s.__table__.columns},
                        "text": s.edited_text,
                    }
                )
            )
        else:
            kept.append(s)
    return kept


def render_publish_html(record: OutputRecord, source_filename: str) -> str:
    """The deliverable: the text as it should go out, no verdict furniture.

    Deliberately separate from the evidence record. The annotated version is for
    sign-off; pasting badges and claim ids into a newsroom CMS is not what anyone
    wants, and offering only that was why the tool had no usable output.
    """
    sentences = _publishable(record)
    return _env.get_template("publish.html").render(
        title=record.title,
        output_type=record.output_type,
        language=record.language,
        is_video=record.output_type == "VIDEO_SCRIPT",
        scenes=sentences,
        sections=[
            (section, list(group)) for section, group in groupby(sentences, key=lambda s: s.section)
        ],
        citation=citation_for(source_filename),
    )


def render_html(record: OutputRecord, source_filename: str) -> str:
    return _env.get_template("output.html").render(
        title=record.title,
        # The exported artefact carries the headline's verdict too: a reader who only
        # ever sees the PDF should know whether its title was verified.
        title_verdict=record.title_verdict,
        title_confidence=record.title_confidence,
        title_claim_ids=record.title_claim_ids,
        output_type=record.output_type,
        language=record.language,
        coverage=record.coverage,
        is_video=record.output_type == "VIDEO_SCRIPT",
        scenes=sorted(record.sentences, key=lambda s: s.order_index),
        sections=_sections(record),
        citation=citation_for(source_filename),
    )


def render_pdf(record: OutputRecord, source_filename: str) -> bytes:
    from weasyprint import HTML  # lazy: needs system libs

    return HTML(string=render_html(record, source_filename)).write_pdf()


def render_publish_pdf(record: OutputRecord, source_filename: str) -> bytes:
    from weasyprint import HTML  # lazy: needs system libs

    return HTML(string=render_publish_html(record, source_filename)).write_pdf()
