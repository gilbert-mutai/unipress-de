"""Per-sentence verification (docs/03 §5): Tier-1 NLI -> gating -> Tier-2 judge -> score.

Flow per factual sentence:
  1. numeric mismatch                          -> CONTRADICTED (hard)
  2. NLI contradiction > cutoff                -> CONTRADICTED
  3. gate to the judge if it's numeric or Tier-1 entailment is not clearly high
  4. confidence = blend(entail, judge_supported, overlap) - numeric penalty
  5. threshold -> SUPPORTED / INTERPRETATION / UNSUPPORTED
Non-factual sentences (hooks, connectives) are RHETORICAL and skipped.
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


def verify_output(output: GeneratedOutput, claims_by_key: dict[str, ClaimEvidence]) -> None:
    """Mutate each sentence in-place with a verdict, confidence, and rationale."""
    s = get_settings()
    entailment = get_entailment()
    use_judge = judge_enabled()

    for sentence in output.sentences:
        if not sentence.is_factual:
            sentence.verdict = Verdict.RHETORICAL
            sentence.confidence = None
            continue

        cited = [claims_by_key[k] for k in sentence.claim_ids if k in claims_by_key]
        if not cited:
            sentence.verdict = Verdict.UNSUPPORTED
            sentence.confidence = 0.0
            sentence.rationale = "no cited claim found in the source"
            continue

        premise = " ".join(c.quote for c in cited)
        numeric_bad = numeric_mismatch(sentence.text, premise)
        scores = entailment.classify(premise, sentence.text)

        # Hard fails first.
        if numeric_bad:
            sentence.verdict = Verdict.CONTRADICTED
            sentence.confidence = round(
                confidence(scores.entail, quote_overlap(sentence.text, premise), True), 3
            )
            sentence.rationale = "a number is not corroborated by the cited source"
            continue
        if scores.contradict > s.trust_contradict_cutoff:
            sentence.verdict = Verdict.CONTRADICTED
            sentence.confidence = round(1.0 - scores.contradict, 3)
            sentence.rationale = "the cited source appears to contradict this statement"
            continue

        # Tier-2 gating: judge numeric statements and anything not clearly entailed.
        judge_supported: float | None = None
        has_numbers = bool(numbers(sentence.text))
        if use_judge and (has_numbers or scores.entail < s.trust_entail_high):
            result = get_judge().judge(premise, sentence.text)
            judge_supported = result.supported_fraction
            sentence.rationale = result.rationale or None
            if result.label == "contradicted":
                sentence.verdict = Verdict.CONTRADICTED
                sentence.confidence = round(min(0.2, judge_supported), 3)
                continue

        overlap = quote_overlap(sentence.text, premise)
        score = confidence(scores.entail, overlap, False, judge_supported)
        sentence.confidence = round(score, 3)

        if score >= s.trust_export_threshold:
            sentence.verdict = (
                Verdict.SUPPORTED if sentence.role == SentenceRole.FACT else Verdict.INTERPRETATION
            )
        elif score >= s.trust_low_threshold:
            sentence.verdict = Verdict.INTERPRETATION
            if not sentence.rationale:
                sentence.rationale = "partially grounded; reasonable interpretation"
        else:
            sentence.verdict = Verdict.UNSUPPORTED
            if not sentence.rationale:
                sentence.rationale = "insufficient grounding in the cited source"
