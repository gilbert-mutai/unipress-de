"""The CI eval-gate must pass clean metrics and FAIL on an injected regression (docs/05 §8)."""

from __future__ import annotations

import run_eval


def test_gate_passes_on_clean_metrics() -> None:
    agg = {"hallucination_rate": 0.0, "faithfulness": 1.0, "evidence_link_validity": 1.0}
    checks = run_eval._target_check(agg)
    assert checks, "expected target checks"
    assert all(c["met"] for c in checks)


def test_gate_fails_on_injected_hallucination_regression() -> None:
    # Simulate a model regression: hallucination spikes, faithfulness drops below the bar.
    agg = {"hallucination_rate": 0.20, "faithfulness": 0.70, "evidence_link_validity": 1.0}
    missed = [c["metric"] for c in run_eval._target_check(agg) if not c["met"]]
    assert "hallucination_rate" in missed
    assert "faithfulness" in missed
    assert "evidence_link_validity" not in missed  # this one still meets its bar
