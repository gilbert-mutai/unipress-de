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


def test_numeric_mismatch_reads_hungarian_decimal_commas() -> None:
    """HU writes 88,8 where the EN source writes 88.8 — that is not a mismatch.

    Reading every comma as a thousands separator turned 88,8 into 888 and made
    the TrustLayer return CONTRADICTED for correct Hungarian sentences.
    """
    assert numeric_mismatch("A pontosság 88,8% volt.", PREMISE) is False
    assert numeric_mismatch("339 kenetet vizsgáltak.", PREMISE) is False
    # …and a genuinely wrong Hungarian number is still caught.
    assert numeric_mismatch("A pontosság 98,8% volt.", PREMISE) is True


def test_numeric_mismatch_still_reads_english_thousands_separators() -> None:
    premise = "The ensemble produced 12,000,000 cell predictions across 1,234 slides."
    assert numeric_mismatch("It made 12,000,000 predictions.", premise) is False
    assert numeric_mismatch("Across 1,234 slides.", premise) is False
    assert numeric_mismatch("Across 9,999 slides.", premise) is True


def test_numeric_mismatch_ignores_digits_inside_identifiers() -> None:
    """A leaked "(clm_003, clm_005)" citation is not a numeric claim.

    Reading the digits out of clm_003 hard-failed correct sentences to
    CONTRADICTED — observed in production on the Hungarian video script.
    """
    assert numeric_mismatch("It raises capacity (clm_003, clm_005).", PREMISE) is False
    assert numeric_mismatch("88,8%-os pontosság (clm_002, clm_024).", PREMISE) is False


def test_numeric_mismatch_reads_spelled_out_numbers_in_the_source() -> None:
    """The paper writes "nine networks"; a translated sentence writes "9"."""
    premise = "The system used an ensemble of nine deep neural networks."
    assert numeric_mismatch("A 9 modellből álló háló.", premise) is False
    assert numeric_mismatch("An ensemble of 9 networks.", premise) is False
    assert numeric_mismatch("An ensemble of 42 networks.", premise) is True


def test_prose_words_are_not_numeric_obligations() -> None:
    """Hungarian "egy" is the indefinite article, not a claim that something is 1.

    Expanding number words on the *sentence* side turned "Egy új tanulmány
    szerint…" ("A new study…") into "1 új tanulmány" and hard-failed it. Only the
    premise is expanded, so prose like this carries no numeric obligation.
    """
    assert numeric_mismatch("Egy új tanulmány szerint a rendszer segít.", PREMISE) is False
    assert numeric_mismatch("A szűrés egy munkaigényes folyamat.", PREMISE) is False
    assert numeric_mismatch("Kilenc modellt alkalmaz.", PREMISE) is False
    # An actual numeral in the sentence is still checked.
    assert numeric_mismatch("A rendszer 9 modellt alkalmaz.", PREMISE) is True


def test_numeric_mismatch_handles_mixed_separators() -> None:
    """Both conventions for one thousand and a bit."""
    assert numeric_mismatch("Total was 1.234,5 units.", "Total was 1,234.5 units.") is False
    assert numeric_mismatch("Total was 9.999,5 units.", "Total was 1,234.5 units.") is True


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


def test_lexical_classify_has_no_contradiction_signal() -> None:
    from app.trustlayer.entailment import LexicalEntailment

    scores = LexicalEntailment().classify("cats are mammals with fur", "cats are mammals")
    assert scores.entail > 0.9
    assert scores.contradict == 0.0  # the lexical proxy cannot detect contradiction


def test_judge_supported_feeds_confidence_and_rationale(monkeypatch) -> None:
    from app.trustlayer import verify as V
    from app.trustlayer.judge import JudgeResult

    monkeypatch.setattr(V, "judge_enabled", lambda: True)

    class FakeJudge:
        def judge(self, source: str, statement: str) -> JudgeResult:
            return JudgeResult(
                label="supported", supported_fraction=1.0, rationale="verified by judge"
            )

    monkeypatch.setattr(V, "get_judge", lambda: FakeJudge())

    claims = {"clm_001": ClaimEvidence("clm_001", "Domestic cats are small carnivorous mammals.")}
    # Low lexical overlap alone would flag this; the judge's supported_fraction rescues it.
    out = _output(
        GeneratedSentence(
            text="Felines are animals.", role=SentenceRole.FACT, claim_ids=["clm_001"]
        )
    )
    V.verify_output(out, claims)
    assert out.sentences[0].rationale == "verified by judge"
    assert out.sentences[0].confidence and out.sentences[0].confidence >= 0.4


def test_judge_contradiction_hard_fails(monkeypatch) -> None:
    from app.trustlayer import verify as V
    from app.trustlayer.judge import JudgeResult

    monkeypatch.setattr(V, "judge_enabled", lambda: True)
    monkeypatch.setattr(
        V,
        "get_judge",
        lambda: type(
            "J", (), {"judge": lambda self, s, t: JudgeResult("contradicted", 0.0, "no")}
        )(),
    )
    claims = {"clm_001": ClaimEvidence("clm_001", "The study found no effect.")}
    out = _output(
        GeneratedSentence(
            text="The study found a large effect.", role=SentenceRole.FACT, claim_ids=["clm_001"]
        )
    )
    V.verify_output(out, claims)
    assert out.sentences[0].verdict == Verdict.CONTRADICTED


def test_coverage_flags_dropped_limitation() -> None:
    from app.generation.fallback import ClaimInput
    from app.trustlayer.coverage import coverage_report

    claims = [
        ClaimInput("clm_001", "A key finding.", "FINDING", 0.9),
        ClaimInput("clm_002", "Only tested on born-digital images.", "LIMITATION", 0.8),
    ]
    out = _output(
        GeneratedSentence(text="A key finding.", role=SentenceRole.FACT, claim_ids=["clm_001"])
    )
    report = coverage_report(claims, out)
    assert "clm_002" in report["dropped_limitations"]
    assert "clm_001" in report["cited"]
    assert report["warnings"]
