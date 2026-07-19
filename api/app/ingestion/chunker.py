"""Structure-aware chunking: parsed blocks -> retrieval chunks with source spans.

Design choices that keep provenance exact and UI-highlightable:
- Chunks never cross a page boundary, so each chunk has one page + one bbox.
- A chunk is a run of consecutive text blocks, so its text is a verbatim
  substring of the page text; `char_start/char_end` index into that page's text
  and `quote` is exactly `page_text[char_start:char_end]`.
- A best-effort running `section` label is attached (nullable per docs/03 §1.1).
"""

from __future__ import annotations

import re

from app.ingestion.models import Block, Chunk, ParsedDoc, SourceSpan

# Target/max chunk size in characters (block-aligned, so these are soft bounds).
_TARGET_CHARS = 900
_MAX_CHARS = 1400

_SECTION_KEYWORDS = {
    "abstract",
    "introduction",
    "background",
    "related work",
    "materials and methods",
    "methods",
    "methodology",
    "experiments",
    "experimental setup",
    "results",
    "results and discussion",
    "discussion",
    "conclusion",
    "conclusions",
    "limitations",
    "references",
    "acknowledgements",
    "acknowledgments",
    "appendix",
}

_NUMBERED_HEADING = re.compile(r"^\d+(\.\d+)*\.?\s+[A-Z][^.!?]{2,60}$")


def _detect_section(text: str) -> str | None:
    """Return a normalized section label if `text` looks like a heading, else None."""
    line = text.strip().splitlines()[0].strip() if text.strip() else ""
    if not line or len(line) > 80:
        return None
    low = line.lower().rstrip(":")
    if low in _SECTION_KEYWORDS:
        return line.rstrip(":")
    if _NUMBERED_HEADING.match(line):
        return line
    return None


def _union_bbox(blocks: list[Block]) -> list[float]:
    x0 = min(b.bbox[0] for b in blocks)
    y0 = min(b.bbox[1] for b in blocks)
    x1 = max(b.bbox[2] for b in blocks)
    y1 = max(b.bbox[3] for b in blocks)
    return [x0, y0, x1, y1]


def _make_chunk(
    index: int, doc_id: str, page: int, section: str | None, start: int, blocks: list[Block]
) -> Chunk:
    text = "\n".join(b.text for b in blocks)
    span = SourceSpan(
        doc_id=doc_id,
        page=page,
        section=section,
        char_start=start,
        char_end=start + len(text),
        quote=text,
        bbox=_union_bbox(blocks),
    )
    return Chunk(index=index, text=text, span=span, token_estimate=len(text) // 4)


def chunk_document(parsed: ParsedDoc) -> list[Chunk]:
    """Produce ordered, span-linked chunks for a parsed document."""
    chunks: list[Chunk] = []
    section: str | None = None

    for page in parsed.pages:
        # Reconstruct per-block offsets into page.text (blocks joined by "\n").
        offset = 0
        block_offsets: list[int] = []
        for b in page.blocks:
            block_offsets.append(offset)
            offset += len(b.text) + 1  # +1 for the "\n" separator

        pending: list[Block] = []
        pending_start = 0

        for b, start in zip(page.blocks, block_offsets, strict=True):
            heading = _detect_section(b.text)
            if heading is not None:
                # Heading ends the current run and starts a new section. Keep the
                # heading as its own small chunk to anchor retrieval.
                if pending:
                    chunks.append(
                        _make_chunk(
                            len(chunks), parsed.doc_id, page.number, section, pending_start, pending
                        )
                    )
                    pending = []
                section = heading
                chunks.append(
                    _make_chunk(len(chunks), parsed.doc_id, page.number, section, start, [b])
                )
                continue

            cur_len = sum(len(x.text) + 1 for x in pending)
            if pending and cur_len + len(b.text) > _MAX_CHARS:
                chunks.append(
                    _make_chunk(
                        len(chunks), parsed.doc_id, page.number, section, pending_start, pending
                    )
                )
                pending = []
            if not pending:
                pending_start = start
            pending.append(b)
            if sum(len(x.text) + 1 for x in pending) >= _TARGET_CHARS:
                chunks.append(
                    _make_chunk(
                        len(chunks), parsed.doc_id, page.number, section, pending_start, pending
                    )
                )
                pending = []

        if pending:
            chunks.append(
                _make_chunk(
                    len(chunks), parsed.doc_id, page.number, section, pending_start, pending
                )
            )

    return chunks
