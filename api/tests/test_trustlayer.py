"""TrustLayer unit tests: the deterministic verification core."""

from __future__ import annotations

from app.generation.models import (
    GeneratedOutput,
    GeneratedSentence,
    OutputType,
    SentenceRole,
    Verdict,
)
from app.trustlayer.numeric import numeric_mismatch
from app.trustlayer.verify import ClaimEvidence, verify_output

PREMISE = "The method reached 88.8% accuracy on 339 smears."


def test_numeric_mismatch_catches_wrong_number() -> None:
    assert numeric_mismatch("It reached 98.8% accuracy.", PREMISE) is True  # 88.8 -> 98.8
    assert numeric_mismatch("Evaluated on 339 smears.", PREMISE) is False
    assert numeric_mismatch("Accuracy was nearly 90%.", PREMISE) is False  # rounding tolerated
    assert numeric_mismatch("A qualitative improvement.", PREMISE) is False  # no numbers


def _output(*sentences: GeneratedSentence) -> GeneratedOutput:
    return GeneratedOutput(
        output_type=OutputType.PRESS_RELEASE, language="en", title="t", sentences=list(sentences)
    )


def test_verify_assigns_verdicts() -> None:
    claims = {"clm_001": ClaimEvidence("clm_001", PREMISE)}
    out = _output(
        GeneratedSentence(text=PREMISE, role=SentenceRole.FACT, claim_ids=["clm_001"]),
        GeneratedSentence(
            text="It reached 98.8% accuracy.", role=SentenceRole.FACT, claim_ids=["clm_001"]
        ),
        GeneratedSentence(
            text="A totally unrelated statement about weather.",
            role=SentenceRole.FACT,
            claim_ids=["clm_999"],  # unknown claim
        ),
        GeneratedSentence(text="In a breakthrough for science,", role=SentenceRole.RHETORICAL),
    )
    verify_output(out, claims)

    assert out.sentences[0].verdict == Verdict.SUPPORTED
    assert out.sentences[0].confidence and out.sentences[0].confidence >= 0.7
    # numeric hallucination is a hard fail
    assert out.sentences[1].verdict == Verdict.CONTRADICTED
    assert out.sentences[1].confidence < 0.7
    # citing a claim that doesn't exist => unsupported
    assert out.sentences[2].verdict == Verdict.UNSUPPORTED
    # framing carries no factual load
    assert out.sentences[3].verdict == Verdict.RHETORICAL
