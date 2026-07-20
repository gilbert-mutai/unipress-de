"""Confidence scoring (docs/03 §5.4).

    confidence = w1*P_entail + w2*judge_supported + w3*quote_overlap  - numeric_penalty

Until the LLM judge lands (Phase 2b) `judge_supported` is None and its weight is
redistributed across the available signals. A numeric mismatch applies a hard
penalty that drives confidence down regardless of the other signals.
"""

from __future__ import annotations

from app.core.settings import get_settings
from app.trustlayer.entailment import content_tokens


def quote_overlap(sentence: str, premise: str) -> float:
    """Share of the sentence's content words present in the cited premise."""
    sent = content_tokens(sentence)
    if not sent:
        return 1.0
    prem = set(content_tokens(premise))
    return sum(1 for t in sent if t in prem) / len(sent)


def confidence(
    p_entail: float,
    quote_ovl: float,
    numeric_bad: bool,
    judge_supported: float | None = None,
) -> float:
    s = get_settings()
    if judge_supported is None:
        total = s.trust_w1 + s.trust_w3 or 1.0
        base = (s.trust_w1 * p_entail + s.trust_w3 * quote_ovl) / total
    else:
        base = s.trust_w1 * p_entail + s.trust_w2 * judge_supported + s.trust_w3 * quote_ovl
    if numeric_bad:
        base -= s.trust_numeric_penalty
    return max(0.0, min(1.0, base))
