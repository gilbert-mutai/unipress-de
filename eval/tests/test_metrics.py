"""Unit tests for the pure evaluation metrics (docs/05)."""

from __future__ import annotations

import metrics


def _s(role: str, verdict: str | None = None, conf: float | None = None,
       claims: list[str] | None = None, text: str = "x") -> dict:
    return {"role": role, "verdict": verdict, "confidence": conf,
            "claim_ids": claims or [], "text": text}


def test_hallucination_rate_counts_unsupported_and_contradicted() -> None:
    sents = [
        _s("FACT", "SUPPORTED", 0.9, ["c1"]),
        _s("FACT", "CONTRADICTED", 0.1, ["c2"]),
        _s("INTERPRETATION", "UNSUPPORTED", 0.2, ["c3"]),
        _s("RHETORICAL"),  # not factual → excluded from the denominator
    ]
    assert metrics.hallucination_rate(sents) == 2 / 3


def test_hallucination_rate_empty_is_zero() -> None:
    assert metrics.hallucination_rate([_s("RHETORICAL")]) == 0.0


def test_claim_precision_supported_over_factual() -> None:
    sents = [_s("FACT", "SUPPORTED", 0.9), _s("FACT", "UNSUPPORTED", 0.1)]
    assert metrics.claim_precision(sents) == 0.5


def test_faithfulness_is_mean_confidence_of_factual() -> None:
    sents = [_s("FACT", "SUPPORTED", 0.8), _s("FACT", "SUPPORTED", 0.6), _s("RHETORICAL", None, 0.0)]
    assert metrics.faithfulness(sents) == 0.7


def test_evidence_link_validity_flags_dangling_citations() -> None:
    sents = [_s("FACT", "SUPPORTED", 0.9, ["c1"]), _s("FACT", "SUPPORTED", 0.9, ["ghost"])]
    assert metrics.evidence_link_validity(sents, {"c1"}) == 0.5


def test_readability_band_hit_for_simple_english() -> None:
    sents = [_s("FACT", text="The cat sat on the mat. The dog ran fast.")]
    r = metrics.readability(sents, "en", "SOCIAL")
    assert r["method"] == "flesch"
    assert r["band_hit"] is True


def test_coverage_none_without_gold() -> None:
    cov = metrics.coverage([_s("FACT", "SUPPORTED", 0.9, ["c1"])], [])
    assert cov["coverage"] is None


def test_coverage_matches_cited_key_facts() -> None:
    sents = [_s("FACT", "SUPPORTED", 0.9, ["c1", "c2"])]
    cov = metrics.coverage(sents, ["c1", "c3"])
    assert cov["coverage"] == 0.5
    assert cov["missed"] == ["c3"]


def test_quality_score_redistributes_weight_without_coverage() -> None:
    perfect = metrics.quality_score(faith=1.0, halluc=0.0, cov=None, evidence=1.0,
                                    readability_band_hit=True)
    assert perfect == 100.0


def test_quality_score_penalizes_hallucination() -> None:
    q = metrics.quality_score(faith=0.5, halluc=0.5, cov=None, evidence=1.0,
                              readability_band_hit=False)
    assert 0.0 <= q < 100.0


def test_adversarial_caught_rate() -> None:
    res = [
        {"id": "adv1", "expect": "CONTRADICTED", "verdict": "CONTRADICTED"},
        {"id": "adv2", "expect": "CONTRADICTED", "verdict": "SUPPORTED"},  # missed
    ]
    out = metrics.adversarial_caught(res)
    assert out["caught_rate"] == 0.5
    assert out["missed"] == ["adv2"]
