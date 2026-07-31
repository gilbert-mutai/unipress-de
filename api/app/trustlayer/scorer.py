"""Confidence scoring (docs/03 §5.4).

    confidence = w1*P_entail + w2*judge_supported + w3*quote_overlap  - numeric_penalty

A signal that could not be measured has its weight redistributed across the ones
that could, rather than counting as zero support:

- `judge_supported` is None when the Tier-2 judge is disabled or was not gated in.
- `quote_overlap` is meaningless when the output language differs from the source's.
  A Hungarian sentence shares almost no content words with an English quote, so the
  term scored ~0 for every Hungarian sentence and cost it roughly a third of the
  blend. That is absence of measurement, not evidence of ungroundedness — and it
  is why Hungarian outputs ran 0.38–0.62 against English's 0.58–0.89 on the same
  claims. Redistribution cannot invent support: if entailment and the judge are
  both low, the renormalised score stays low.

A numeric mismatch applies a hard penalty regardless of the other signals.
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
    *,
    lexical_comparable: bool = True,
) -> float:
    """Blend the trust signals into one confidence.

    `lexical_comparable=False` drops the quote-overlap term and renormalises,
    for text written in a different language from the source it cites.
    """
    s = get_settings()
    w1, w2, w3 = s.trust_w1, s.trust_w2, s.trust_w3
    if not lexical_comparable:
        w3 = 0.0

    weighted = w1 * p_entail
    total = w1
    if judge_supported is not None:
        weighted += w2 * judge_supported
        total += w2
    if w3:
        weighted += w3 * quote_ovl
        total += w3

    base = weighted / (total or 1.0)
    if numeric_bad:
        base -= s.trust_numeric_penalty
    return max(0.0, min(1.0, base))
