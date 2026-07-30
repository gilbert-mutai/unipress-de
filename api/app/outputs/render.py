"""Render a generated output to HTML (Jinja2) or PDF (WeasyPrint).

HTML is dependency-light and always available (the review UI and tests use it).
PDF is produced by WeasyPrint, imported lazily because it needs system libraries
(pango/cairo) present in the container; unavailable environments raise a clear error.
"""

from __future__ import annotations

from itertools import groupby
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.db_models import OutputRecord
from app.outputs.manifest import attribution_for

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
        attribution=attribution_for(source_filename),
    )


def render_pdf(record: OutputRecord, source_filename: str) -> bytes:
    from weasyprint import HTML  # lazy: needs system libs

    return HTML(string=render_html(record, source_filename)).write_pdf()
