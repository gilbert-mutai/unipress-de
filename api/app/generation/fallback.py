"""Deterministic claim-bound generator — no LLM required.

Composes a structured output directly from the verified claim store: each factual
sentence is a claim rendered verbatim and cites that claim's key, so the output is
trivially grounded (and the pipeline/tests run with no API key). The LLM generator
(llm_generator.py) does real audience-adapted rewriting behind the same contract;
this baseline proves the claim-binding structure end to end.
"""

from __future__ import annotations

from app.claims.models import ClaimType
from app.generation.models import (
    GeneratedOutput,
    GeneratedSentence,
    OutputSpec,
    OutputType,
    SentenceRole,
)


class ClaimInput:
    """Minimal view of a claim the generator needs."""

    def __init__(self, key: str, text: str, claim_type: str, importance: float) -> None:
        self.key = key
        self.text = text
        self.claim_type = claim_type
        self.importance = importance


def _by_type(claims: list[ClaimInput], claim_type: str) -> list[ClaimInput]:
    return [c for c in claims if c.claim_type == claim_type]


def generate_fallback(
    spec: OutputSpec, claims: list[ClaimInput], language: str, title_hint: str
) -> GeneratedOutput:
    if spec.output_type == OutputType.VIDEO_SCRIPT:
        from app.generation.video import build_video_scenes

        return build_video_scenes(claims, language, title_hint)

    eligible = [c for c in claims if c.claim_type in spec.claim_types]
    eligible.sort(key=lambda c: c.importance, reverse=True)
    eligible = eligible[: spec.max_claims]

    findings = _by_type(eligible, ClaimType.FINDING) or eligible
    quant = _by_type(eligible, ClaimType.QUANTITATIVE)
    limitations = _by_type(eligible, ClaimType.LIMITATION)

    sentences: list[GeneratedSentence] = []
    headline = findings[0] if findings else (eligible[0] if eligible else None)
    title = headline.text if headline else title_hint

    if headline:
        sentences.append(
            GeneratedSentence(
                text=headline.text,
                role=SentenceRole.FACT,
                claim_ids=[headline.key],
                section="headline",
            )
        )
    # Body: remaining findings + key quantitative claims.
    body = [c for c in (findings[1:] + quant) if not headline or c.key != headline.key]
    for c in body[:6]:
        sentences.append(
            GeneratedSentence(
                text=c.text, role=SentenceRole.FACT, claim_ids=[c.key], section="body"
            )
        )
    # Honest caveat from a limitation, if present.
    if limitations:
        sentences.append(
            GeneratedSentence(
                text=limitations[0].text,
                role=SentenceRole.FACT,
                claim_ids=[limitations[0].key],
                section="caveat",
            )
        )

    return GeneratedOutput(
        output_type=spec.output_type,
        language=language,
        title=title,
        sentences=sentences,
    )
