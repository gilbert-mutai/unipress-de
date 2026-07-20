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
}


def get_spec(output_type: OutputType) -> OutputSpec:
    if output_type not in SPECS:
        raise ValueError(f"no spec for output type {output_type} (not in MVP set yet)")
    return SPECS[output_type]
