"""Claim data contracts (docs/03 §1.2, §2.2)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.ingestion.models import SourceSpan


class ClaimType(StrEnum):
    EXPLICIT_FACT = "EXPLICIT_FACT"  # stated directly in the source
    QUANTITATIVE = "QUANTITATIVE"  # a fact containing a number/statistic
    FINDING = "FINDING"  # the paper's own conclusion/claim
    METHOD = "METHOD"  # what was done
    LIMITATION = "LIMITATION"  # a stated caveat/constraint
    BACKGROUND = "BACKGROUND"  # context / prior work


class Claim(BaseModel):
    """An atomic, checkable statement bound to a quote-verified source span."""

    key: str  # human id within a document, e.g. "clm_001"
    text: str  # atomic, self-contained
    claim_type: ClaimType
    span: SourceSpan  # provenance (quote-verified)
    entities: list[str] = Field(default_factory=list)
    importance: float = 0.5  # 0–1, for coverage weighting
    numeric: bool = False  # contains a number/statistic (higher scrutiny)
