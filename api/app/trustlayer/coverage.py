"""Document-level coverage check (docs/03 §5.5).

Of the most important claims, how many made it into the output? Omitted
high-importance claims — and especially dropped LIMITATIONs — are surfaced as
warnings so a reviewer knows when a caveat was silently left out.
"""

from __future__ import annotations

from app.claims.models import ClaimType
from app.generation.fallback import ClaimInput
from app.generation.models import GeneratedOutput

_TOP_N = 5


def coverage_report(claims: list[ClaimInput], output: GeneratedOutput) -> dict:
    cited = {
        cid
        for sentence in output.sentences
        if sentence.is_factual
        for cid in (sentence.claim_ids or [])
    }
    ranked = sorted(claims, key=lambda c: c.importance, reverse=True)
    important = [c.key for c in ranked[:_TOP_N]]
    omitted_important = [k for k in important if k not in cited]
    dropped_limitations = [
        c.key for c in claims if c.claim_type == ClaimType.LIMITATION and c.key not in cited
    ]

    warnings: list[str] = []
    if dropped_limitations:
        warnings.append(
            f"{len(dropped_limitations)} limitation claim(s) omitted — a caveat was dropped"
        )
    if omitted_important:
        warnings.append(f"{len(omitted_important)} high-importance claim(s) omitted")

    return {
        "cited": sorted(cited),
        "omitted_important": omitted_important,
        "dropped_limitations": dropped_limitations,
        "warnings": warnings,
    }
