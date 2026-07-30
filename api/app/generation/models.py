"""Generation + verification contracts (docs/03 §1.3–1.4, docs/04)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class OutputType(StrEnum):
    PRESS_RELEASE = "PRESS_RELEASE"
    ARTICLE = "ARTICLE"
    SOCIAL = "SOCIAL"
    EXEC_SUMMARY = "EXEC_SUMMARY"
    VIDEO_SCRIPT = "VIDEO_SCRIPT"


class SentenceRole(StrEnum):
    FACT = "FACT"  # asserts something; must cite claim_ids and be verified
    INTERPRETATION = "INTERPRETATION"  # reasonable inference; verified, softer
    RHETORICAL = "RHETORICAL"  # framing/hook; no factual load
    TRANSITION = "TRANSITION"  # connective; no factual load


class Verdict(StrEnum):
    SUPPORTED = "SUPPORTED"
    INTERPRETATION = "INTERPRETATION"
    RHETORICAL = "RHETORICAL"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTED = "CONTRADICTED"


_FACTUAL_ROLES = {SentenceRole.FACT, SentenceRole.INTERPRETATION}


class GeneratedSentence(BaseModel):
    text: str  # for a video scene, this is the spoken narration
    role: SentenceRole = SentenceRole.FACT
    claim_ids: list[str] = Field(default_factory=list)  # claim keys, e.g. ["clm_003"]
    section: str | None = None  # structure slot (headline/lead/body/caveat, or a video scene)
    # Video-script scene metadata (None for prose outputs):
    timecode: str | None = None  # e.g. "0:20–0:45"
    on_screen: str | None = None  # short on-screen text
    visual: str | None = None  # visual suggestion, e.g. "show Figure 2"
    # Filled by the TrustLayer:
    verdict: Verdict | None = None
    confidence: float | None = None
    rationale: str | None = None

    @property
    def is_factual(self) -> bool:
        return self.role in _FACTUAL_ROLES


class GeneratedOutput(BaseModel):
    output_type: OutputType
    language: Literal["en", "hu"]
    title: str
    sentences: list[GeneratedSentence]
    # The headline is the most-read and most-quotable line in an output, so it is
    # claim-bound and verified like any factual sentence. Leaving it unchecked let
    # a simulation-only study be titled "Achieves 100% Success Rate" while the
    # body sentences citing the same claims scored only INTERPRETATION.
    title_claim_ids: list[str] = Field(default_factory=list)
    title_verdict: Verdict | None = None
    title_confidence: float | None = None
    title_rationale: str | None = None


class OutputSpec(BaseModel):
    """The per-type generation contract (docs/04 §1)."""

    output_type: OutputType
    tone: str
    length_target: str
    structure: list[str]
    must_include: list[str] = Field(default_factory=list)
    must_avoid: list[str] = Field(default_factory=list)
    claim_types: list[str] = Field(default_factory=list)  # eligible ClaimType values
    max_claims: int = 12
