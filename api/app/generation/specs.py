"""Per-output-type specifications (docs/04). Adding an output = adding a spec."""

from __future__ import annotations

from app.claims.models import ClaimType
from app.generation.models import OutputSpec, OutputType

SPECS: dict[OutputType, OutputSpec] = {
    OutputType.PRESS_RELEASE: OutputSpec(
        output_type=OutputType.PRESS_RELEASE,
        tone="authoritative, newsworthy, accessible; no hype",
        length_target="350-500 words",
        structure=["headline", "lead", "body", "caveat"],
        must_include=["headline finding", "who", "why it matters"],
        must_avoid=["jargon", "unverified numbers", "hype", "fabricated quotes"],
        claim_types=[ClaimType.FINDING, ClaimType.QUANTITATIVE, ClaimType.LIMITATION],
        max_claims=10,
    ),
    OutputType.EXEC_SUMMARY: OutputSpec(
        output_type=OutputType.EXEC_SUMMARY,
        tone="concise, neutral, decision-oriented",
        length_target="150-250 words",
        structure=["takeaway", "results", "limitations"],
        must_include=["headline finding", "key numbers", "limitations"],
        must_avoid=["rhetorical framing", "hype"],
        claim_types=[
            ClaimType.FINDING,
            ClaimType.QUANTITATIVE,
            ClaimType.LIMITATION,
            ClaimType.METHOD,
        ],
        max_claims=10,
    ),
    OutputType.ARTICLE: OutputSpec(
        output_type=OutputType.ARTICLE,
        tone="engaging, explanatory, warm but accurate",
        length_target="600-900 words",
        structure=["hook", "why it matters", "what they did", "what they found", "limits"],
        must_include=["plain-language explanation", "why it matters"],
        must_avoid=["unexplained jargon", "oversimplification that changes meaning"],
        claim_types=[
            ClaimType.FINDING,
            ClaimType.QUANTITATIVE,
            ClaimType.METHOD,
            ClaimType.BACKGROUND,
            ClaimType.LIMITATION,
        ],
        max_claims=14,
    ),
    OutputType.SOCIAL: OutputSpec(
        output_type=OutputType.SOCIAL,
        tone="punchy, professional, accessible",
        length_target="LinkedIn 80-150 words / X <=280 chars",
        structure=["hook", "insight", "why it matters"],
        must_include=["one headline finding"],
        must_avoid=["numbers not from a quantitative claim", "hype"],
        claim_types=[ClaimType.FINDING, ClaimType.QUANTITATIVE],
        max_claims=3,
    ),
    OutputType.VIDEO_SCRIPT: OutputSpec(
        output_type=OutputType.VIDEO_SCRIPT,
        tone="energetic, clear, spoken-word cadence",
        length_target="~140 spoken words (~60s)",
        structure=["hook", "context", "finding", "meaning", "cta"],
        must_include=["hook", "1-2 key claims", "takeaway"],
        must_avoid=["on-screen numbers not from a quantitative claim"],
        claim_types=[ClaimType.FINDING, ClaimType.QUANTITATIVE, ClaimType.LIMITATION],
        max_claims=5,
    ),
}


def get_spec(output_type: OutputType) -> OutputSpec:
    if output_type not in SPECS:
        raise ValueError(f"no spec for output type {output_type} (not in MVP set yet)")
    return SPECS[output_type]
