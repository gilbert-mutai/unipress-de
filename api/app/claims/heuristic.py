"""Deterministic claim extractor — no LLM required.

A pragmatic, dependency-free baseline that keeps the pipeline (and its tests)
runnable without any API key. It splits chunk text into sentences, keeps the
claim-like ones (findings, methods, limitations, and quantitative statements),
types them by cue words, and — crucially — runs every candidate through the
quote-verification guardrail so each stored claim is provably grounded in the
source. The schema-constrained LLM path (app/claims/llm_extractor.py) is the
higher-quality alternative behind the same guardrail; this baseline covers the
common numeric/finding claims that matter most for the demo.
"""

from __future__ import annotations

import re

from app.claims.guardrail import find_span, normalize_ws
from app.claims.models import Claim, ClaimType
from app.ingestion.models import Chunk, SourceSpan

_MIN_SENTENCE = 40
_MAX_SENTENCE = 400
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")

_MEASUREMENT = re.compile(
    r"\d+(\.\d+)?\s?%|\bp\s*[<>=]|\d+(\.\d+)?\s?(percent|points?|images?|samples?|cases?|smears?|frames?)",
    re.IGNORECASE,
)
_FINDING_CUES = (
    "we propose",
    "we present",
    "we introduce",
    "outperform",
    "achiev",
    "improv",
    "demonstrat",
    "results show",
    "results indicate",
    "we find",
    "we show",
    "novel",
    "state-of-the-art",
    "significantly",
    "we obtain",
)
_METHOD_CUES = (
    "we use",
    "we train",
    "was trained",
    "is trained",
    "we implement",
    "we apply",
    "architecture",
    "we develop",
    "our method",
    "our approach",
    "we design",
    "we propose a",
    "based on a",
)
_LIMITATION_CUES = (
    "however",
    "limitation",
    "limited to",
    "cannot",
    "fails to",
    "drawback",
    "future work",
    "not able",
    "remains a challenge",
)

_IMPORTANCE = {
    ClaimType.QUANTITATIVE: 0.85,
    ClaimType.FINDING: 0.8,
    ClaimType.LIMITATION: 0.7,
    ClaimType.METHOD: 0.6,
    ClaimType.EXPLICIT_FACT: 0.5,
    ClaimType.BACKGROUND: 0.3,
}

_ACRONYM = re.compile(r"\b[A-Z][A-Za-z0-9]*[A-Z][A-Za-z0-9]*\b|\b[A-Z]{2,}\b")


def _classify(sentence: str) -> ClaimType | None:
    low = sentence.lower()
    has_measurement = bool(_MEASUREMENT.search(sentence))
    if any(c in low for c in _LIMITATION_CUES):
        return ClaimType.LIMITATION
    if has_measurement:
        return ClaimType.QUANTITATIVE
    if any(c in low for c in _FINDING_CUES):
        return ClaimType.FINDING
    if any(c in low for c in _METHOD_CUES):
        return ClaimType.METHOD
    return None  # not confidently claim-like → skip (LLM path catches the rest)


def _entities(sentence: str) -> list[str]:
    seen: dict[str, None] = {}
    for m in _ACRONYM.findall(sentence):
        if len(m) >= 2:
            seen.setdefault(m, None)
    return list(seen)[:8]


def extract_claims(chunks: list[Chunk], max_claims: int = 80) -> list[Claim]:
    """Extract quote-verified claims from a document's chunks."""
    candidates: list[Claim] = []
    seen_text: set[str] = set()

    for chunk in chunks:
        norm = normalize_ws(chunk.text)
        for sentence in _SENTENCE_SPLIT.split(norm):
            sentence = sentence.strip()
            if not (_MIN_SENTENCE <= len(sentence) <= _MAX_SENTENCE):
                continue
            claim_type = _classify(sentence)
            if claim_type is None:
                continue

            dedup_key = normalize_ws(sentence).lower()
            if dedup_key in seen_text:
                continue

            # Guardrail: the sentence must be locatable in the chunk's raw text.
            local = find_span(chunk.text, sentence)
            if local is None:
                continue
            seen_text.add(dedup_key)
            raw_quote = chunk.text[local[0] : local[1]]
            page_start = chunk.span.char_start + local[0]

            span = SourceSpan(
                doc_id=chunk.span.doc_id,
                page=chunk.span.page,
                section=chunk.span.section,
                char_start=page_start,
                char_end=page_start + len(raw_quote),
                quote=raw_quote,
                bbox=chunk.span.bbox,
            )
            candidates.append(
                Claim(
                    key="",  # assigned after ranking
                    text=sentence,
                    claim_type=claim_type,
                    span=span,
                    entities=_entities(sentence),
                    importance=_IMPORTANCE[claim_type],
                    numeric=bool(re.search(r"\d", sentence)),
                )
            )

    # Keep the strongest, then restore document order for stable numbering.
    candidates.sort(key=lambda c: c.importance, reverse=True)
    kept = candidates[:max_claims]
    kept.sort(key=lambda c: (c.span.page, c.span.char_start))
    for i, claim in enumerate(kept, start=1):
        claim.key = f"clm_{i:03d}"
    return kept
