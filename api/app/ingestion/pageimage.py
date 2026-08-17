"""Render a source PDF page to PNG, optionally highlighting a cited span.

Powers the review UI's "see the real paper with the exact quote glowing" panel —
the strongest traceability visual. Rendering server-side (PyMuPDF) keeps the
frontend simple (just an <img>) and lets us draw the highlight precisely from the
stored bbox (page coordinates in PDF points).
"""

from __future__ import annotations

import fitz  # PyMuPDF

from app.adapters.stubs import LocalStorage
from app.core.db import session_scope
from app.db_models import Document

_ZOOM = 2.0  # default: crisp at the panel's display size
_MAX_ZOOM = 4.0  # bounded — render cost and payload both grow with the square
_HL_STROKE = (0.85, 0.45, 0.05)  # amber border
_HL_FILL = (1.0, 0.86, 0.30)  # amber fill


def render_page_png(
    document_id: str,
    page_number: int,
    bbox: list[float] | None,
    zoom: float = _ZOOM,
) -> bytes:
    """Render a page. `zoom` trades payload for detail.

    The panel loads at the default so a slow connection is not punished; the UI
    asks for a higher zoom only once the reviewer actually magnifies, which is
    what makes small print in a dense paper legible rather than merely bigger.
    """
    zoom = max(1.0, min(_MAX_ZOOM, zoom))
    with session_scope() as s:
        doc = s.get(Document, document_id)
        if doc is None:
            raise ValueError(f"document {document_id} not found")
        content_key = doc.content_key

    data = LocalStorage().get(content_key)
    with fitz.open(stream=data, filetype="pdf") as pdf:
        if not (1 <= page_number <= pdf.page_count):
            raise ValueError(f"page {page_number} out of range (1..{pdf.page_count})")
        page = pdf[page_number - 1]
        if bbox and len(bbox) == 4:
            rect = fitz.Rect(*bbox)
            page.draw_rect(rect, color=_HL_STROKE, fill=_HL_FILL, fill_opacity=0.32, width=1.5)
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return pix.tobytes("png")
