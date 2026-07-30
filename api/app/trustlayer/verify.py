"""Per-sentence verification (docs/03 §5): Tier-1 NLI -> gating -> Tier-2 judge -> score.

Flow per factual sentence:
  1. numeric mismatch                          -> CONTRADICTED (hard)
  2. NLI contradiction > cutoff                -> CONTRADICTED
  3. gate to the judge if it's numeric or Tier-1 entailment is not clearly high
  4. confidence = blend(entail, judge_supported, overlap) - numeric penalty
  5. threshold -> SUPPORTED / INTERPRETATION / UNSUPPORTED
Non-factual sentences (hooks, connectives) are RHETORICAL and skipped.

The output's **title** runs through the same assessment. It is the most-read and
most-quotable line in anything published, so leaving it unverified was the one
hole in the guarantee: a simulation-only study came back titled "Achieves 100%
Success Rate" while the body sentences citing those same claims scored only
INTERPRETATION.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.settings import get_settings
from app.generation.models import GeneratedOutput, SentenceRole, Verdict
from app.trustlayer.entailment import get_entailment
from app.trustlayer.judge import get_judge, judge_enabled
from app.trustlayer.numeric import numbers, numeric_mismatch
from app.trustlayer.scorer import confidence, quote_overlap


@dataclass
class ClaimEvidence:
    key: str
    quote: str


@dataclass
class Assessment:
    verdict: Verdict
    confidence: float | None
    rationale: str | None


def _assess(
    text: str,
    claim_ids: list[str],
    claims_by_key: dict[str, ClaimEvidence],
    *,
    soften: bool,
) -> Assessment:
    """Verify one piece of factual text against the claims it cites.

    `soften` caps the result at INTERPRETATION — used for sentences the generator
    tagged INTERPRETATION rather than FACT. Titles are not softened.
    """
    s = get_settings()
    entailment = get_entailment()
    use_judge = judge_enabled()

    cited = [claims_by_key[k] for k in claim_ids if k in claims_by_key]
    if not cited:
        return Assessment(Verdict.UNSUPPORTED, 0.0, "no cited claim found in the source")

    premise = " ".join(c.quote for c in cited)
    numeric_bad = numeric_mismatch(text, premise)
    scores = entailment.classify(premise, text)

    # Hard fails first.
    if numeric_bad:
        return Assessment(
            Verdict.CONTRADICTED,
            round(confidence(scores.entail, quote_overlap(text, premise), True), 3),
            "a number is not corroborated by the cited source",
        )
    if scores.contradict > s.trust_contradict_cutoff:
        return Assessment(
            Verdict.CONTRADICTED,
            round(1.0 - scores.contradict, 3),
            "the cited source appears to contradict this statement",
        )

    # Tier-2 gating: judge numeric statements and anything not clearly entailed.
    judge_supported: float | None = None
    rationale: str | None = None
    if use_judge and (bool(numbers(text)) or scores.entail < s.trust_entail_high):
        result = get_judge().judge(premise, text)
        judge_supported = result.supported_fraction
        rationale = result.rationale or None
        if result.label == "contradicted":
            return Assessment(Verdict.CONTRADICTED, round(min(0.2, judge_supported), 3), rationale)

    overlap = quote_overlap(text, premise)
    score = round(confidence(scores.entail, overlap, False, judge_supported), 3)

    if score >= s.trust_export_threshold:
        return Assessment(Verdict.INTERPRETATION if soften else Verdict.SUPPORTED, score, rationale)
    if score >= s.trust_low_threshold:
        return Assessment(
            Verdict.INTERPRETATION,
            score,
            rationale or "partially grounded; reasonable interpretation",
        )
    return Assessment(
        Verdict.UNSUPPORTED, score, rationale or "insufficient grounding in the cited source"
    )


def verify_output(output: GeneratedOutput, claims_by_key: dict[str, ClaimEvidence]) -> None:
    """Mutate each sentence — and the title — with a verdict, confidence, rationale."""
    for sentence in output.sentences:
        if not sentence.is_factual:
            sentence.verdict = Verdict.RHETORICAL
            sentence.confidence = None
            continue
        a = _assess(
            sentence.text,
            sentence.claim_ids,
            claims_by_key,
            soften=sentence.role != SentenceRole.FACT,
        )
        sentence.verdict, sentence.confidence, sentence.rationale = (
            a.verdict,
            a.confidence,
            a.rationale,
        )

    if output.title:
        a = _assess(output.title, output.title_claim_ids, claims_by_key, soften=False)
        output.title_verdict = a.verdict
        output.title_confidence = a.confidence
        output.title_rationale = a.rationale
