"""PDF parsing via PyMuPDF: text blocks + bounding boxes, with image-only detection.

Born-digital PDFs give us positional text (bbox) directly, which is what the UI
needs to highlight a source span. Scanned/image-only pages are detected and
flagged as a warning rather than silently producing empty text (OCR is out of
MVP scope — see docs/03 §7).
"""

from __future__ import annotations

import fitz  # PyMuPDF

from app.core.logging import get_logger
from app.ingestion.models import Block, Page, ParsedDoc

log = get_logger("ingestion.parser")

# Below this many extracted characters, a page carrying images is treated as
# image-only (likely scanned) and flagged for the user.
_IMAGE_ONLY_CHAR_THRESHOLD = 40


def parse_pdf(data: bytes, doc_id: str, filename: str) -> ParsedDoc:
    """Parse PDF bytes into a structured, span-ready document."""
    pages: list[Page] = []
    warnings: list[str] = []

    with fitz.open(stream=data, filetype="pdf") as doc:
        page_count = doc.page_count
        for i, page in enumerate(doc, start=1):
            raw_blocks = page.get_text("blocks")  # (x0,y0,x1,y1,text,no,type)
            blocks: list[Block] = []
            for x0, y0, x1, y1, text, _no, block_type in raw_blocks:
                if block_type != 0:  # 0 = text, 1 = image
                    continue
                cleaned = text.strip()
                if not cleaned:
                    continue
                blocks.append(
                    Block(text=cleaned, bbox=[float(x0), float(y0), float(x1), float(y1)])
                )

            page_text = "\n".join(b.text for b in blocks)
            has_images = bool(page.get_images(full=True))
            image_only = len(page_text.strip()) < _IMAGE_ONLY_CHAR_THRESHOLD and has_images
            if image_only:
                warnings.append(f"page {i} appears image-only (scanned); text may be incomplete")

            pages.append(Page(number=i, text=page_text, blocks=blocks, image_only=image_only))

    parsed = ParsedDoc(
        doc_id=doc_id,
        filename=filename,
        page_count=page_count,
        pages=pages,
        warnings=warnings,
    )
    log.info(
        "parsed",
        doc_id=doc_id,
        pages=page_count,
        chars=len(parsed.full_text),
        warnings=len(warnings),
    )
    return parsed
