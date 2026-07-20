"""Per-sentence verification: assign verdict + confidence (docs/03 §5).

Non-factual sentences (hooks, connectives) are RHETORICAL and skipped. Factual
sentences are checked against the concatenated quotes of their cited claims:
a numeric mismatch is a hard CONTRADICTED; missing grounding is UNSUPPORTED;
otherwise the confidence score picks SUPPORTED / INTERPRETATION / UNSUPPORTED.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.settings import get_settings
from app.generation.models import GeneratedOutput, Verdict
from app.trustlayer.entailment import get_entailment
from app.trustlayer.numeric import numeric_mismatch
from app.trustlayer.scorer import confidence, quote_overlap


@dataclass
class ClaimEvidence:
    key: str
    quote: str


def verify_output(output: GeneratedOutput, claims_by_key: dict[str, ClaimEvidence]) -> None:
    """Mutate each sentence in-place with a verdict, confidence, and rationale."""
    s = get_settings()
    entailment = get_entailment()

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
        p_entail = entailment.entail_prob(premise, sentence.text)
        overlap = quote_overlap(sentence.text, premise)
        score = confidence(p_entail, overlap, numeric_bad)
        sentence.confidence = round(score, 3)

        if numeric_bad:
            sentence.verdict = Verdict.CONTRADICTED
            sentence.rationale = "a number is not corroborated by the cited source"
        elif score >= s.trust_export_threshold:
            sentence.verdict = Verdict.SUPPORTED
        elif score >= s.trust_low_threshold:
            sentence.verdict = Verdict.INTERPRETATION
            sentence.rationale = "partially grounded; reasonable interpretation"
        else:
            sentence.verdict = Verdict.UNSUPPORTED
            sentence.rationale = "insufficient grounding in the cited source"
