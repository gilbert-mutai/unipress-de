"""Deterministic 60-second video script as a timed scene table (docs/04 §6).

Maps verified claims onto a fixed narrative arc — hook → context → finding →
meaning → CTA — each scene carrying narration (spoken), on-screen text, a visual
suggestion, a timecode, and claim citations. Narration is a claim rendered
verbatim (so it's grounded and verifiable); the LLM path rewrites it into
spoken-word cadence behind the same contract.
"""

from __future__ import annotations

import re

from app.claims.models import ClaimType
from app.generation.fallback import ClaimInput
from app.generation.models import GeneratedOutput, GeneratedSentence, OutputType, SentenceRole

# scene key, timecode, preferred claim types, visual suggestion
_SCENES: list[tuple[str, str, list[str], str]] = [
    (
        "hook",
        "0:00–0:05",
        [ClaimType.QUANTITATIVE, ClaimType.FINDING],
        "Title card + striking stat",
    ),
    ("context", "0:05–0:20", [ClaimType.BACKGROUND, ClaimType.METHOD], "B-roll: the problem"),
    (
        "finding",
        "0:20–0:45",
        [ClaimType.FINDING, ClaimType.QUANTITATIVE],
        "Show the key figure/result",
    ),
    ("meaning", "0:45–0:55", [ClaimType.FINDING, ClaimType.LIMITATION], "Impact visual"),
]
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?%?")


def _on_screen(text: str) -> str:
    """Short on-screen overlay: the first number if present, else the first words."""
    m = _NUMBER.search(text)
    if m:
        return m.group(0)
    words = text.split()
    return " ".join(words[:5]) + ("…" if len(words) > 5 else "")


def build_video_scenes(claims: list[ClaimInput], language: str, title_hint: str) -> GeneratedOutput:
    pool = sorted(claims, key=lambda c: c.importance, reverse=True)
    used: set[str] = set()
    sentences: list[GeneratedSentence] = []
    title = next((c.text for c in pool if c.claim_type == ClaimType.FINDING), title_hint)

    def take(preferred: list[str]) -> ClaimInput | None:
        for want in preferred:
            for c in pool:
                if c.key not in used and c.claim_type == want:
                    used.add(c.key)
                    return c
        for c in pool:  # fall back to any unused claim
            if c.key not in used:
                used.add(c.key)
                return c
        return None

    for scene, timecode, preferred, visual in _SCENES:
        c = take(preferred)
        if c is None:
            continue
        sentences.append(
            GeneratedSentence(
                text=c.text,
                role=SentenceRole.FACT,
                claim_ids=[c.key],
                section=scene,
                timecode=timecode,
                on_screen=_on_screen(c.text),
                visual=visual,
            )
        )

    # Closing call-to-action — framing, not a factual claim.
    sentences.append(
        GeneratedSentence(
            text="Read the full study — every figure and number is in the paper.",
            role=SentenceRole.RHETORICAL,
            section="cta",
            timecode="0:55–1:00",
            on_screen="Read the paper",
            visual="End card: title + DOI",
        )
    )

    return GeneratedOutput(
        output_type=OutputType.VIDEO_SCRIPT,
        language=language,
        title=title,
        sentences=sentences,
    )
