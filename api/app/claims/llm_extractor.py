"""Schema-constrained LLM claim extraction (docs/03 §2.3), behind the same guardrail.

Opt-in (settings.llm_extraction + a key). For each chunk the model is asked to
return atomic claims with a verbatim `quote`; every returned quote is then run
through the quote-verification guardrail — any claim whose quote is not literally
present in the chunk is rejected as a hallucinated extraction. This path is
exercised only when a key is configured; the heuristic extractor is the default.
"""

from __future__ import annotations

import re

from app.claims.guardrail import find_span
from app.claims.models import Claim, ClaimType
from app.core.logging import get_logger
from app.ingestion.models import Chunk, SourceSpan
from app.llm.gateway import LiteLLMGateway

log = get_logger("claims.llm")

_SYSTEM = (
    "You extract atomic, checkable factual claims from a passage of a research "
    "paper. Each claim must be self-contained (no pronouns) and supported by a "
    "verbatim quote copied exactly from the passage. Classify each as one of: "
    "EXPLICIT_FACT, QUANTITATIVE, FINDING, METHOD, LIMITATION, BACKGROUND. "
    'Return JSON: {"claims":[{"text":..,"quote":..,"claim_type":..,"numeric":true|false}]}. '
    "Do not invent facts, numbers, or names not present in the passage."
)


def _valid_type(value: str) -> ClaimType:
    try:
        return ClaimType(value)
    except ValueError:
        return ClaimType.EXPLICIT_FACT


def extract_claims_llm(chunks: list[Chunk], max_claims: int = 80) -> list[Claim]:
    gateway = LiteLLMGateway()
    claims: list[Claim] = []
    rejected = 0
    seen: set[str] = set()

    for chunk in chunks:
        if len(chunk.text) < 60:
            continue
        payload = gateway.complete_json(_SYSTEM, chunk.text)
        for raw in payload.get("claims", []):
            quote = (raw.get("quote") or "").strip()
            text = (raw.get("text") or "").strip()
            if not quote or not text:
                continue
            local = find_span(chunk.text, quote)  # guardrail
            if local is None:
                rejected += 1
                continue
            dedup = text.lower()
            if dedup in seen:
                continue
            seen.add(dedup)
            raw_quote = chunk.text[local[0] : local[1]]
            page_start = chunk.span.char_start + local[0]
            claims.append(
                Claim(
                    key="",
                    text=text,
                    claim_type=_valid_type(raw.get("claim_type", "")),
                    span=SourceSpan(
                        doc_id=chunk.span.doc_id,
                        page=chunk.span.page,
                        section=chunk.span.section,
                        char_start=page_start,
                        char_end=page_start + len(raw_quote),
                        quote=raw_quote,
                        bbox=chunk.span.bbox,
                    ),
                    importance=0.8 if raw.get("numeric") else 0.6,
                    numeric=bool(raw.get("numeric") or re.search(r"\d", text)),
                )
            )

    log.info("extract.llm.done", kept=len(claims), rejected=rejected)
    claims.sort(key=lambda c: (c.span.page, c.span.char_start))
    claims = claims[:max_claims]
    for i, claim in enumerate(claims, start=1):
        claim.key = f"clm_{i:03d}"
    return claims
