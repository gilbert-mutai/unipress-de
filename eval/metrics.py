"""Evaluation metrics (docs/05 §1, §3, §5).

Pure functions over the ``SentenceRead`` shape (plain dicts: ``role``, ``verdict``,
``confidence``, ``claim_ids``, ``text``) so they are trivially unit-testable and
can consume either the API JSON or an in-process run. No dependency on ``app``.

The gold-independent metrics (hallucination, faithfulness, claim-precision,
evidence-link validity, readability) run on any generated output. The gold-based
metrics (key-fact coverage, false-supported, adversarial-caught) activate only
when a frozen gold set is supplied — see ``eval/gold/`` and ``run_eval.py``.
"""

from __future__ import annotations

from typing import Any

FACTUAL_ROLES = {"FACT", "INTERPRETATION"}
SUPPORTED_VERDICTS = {"SUPPORTED", "INTERPRETATION"}
HALLUCINATED_VERDICTS = {"UNSUPPORTED", "CONTRADICTED"}

Sentence = dict[str, Any]

# Flesch reading-ease floor per output type (higher = easier to read). A sentence
# set clears its band if mean ease >= floor. Exec summaries are allowed to be
# denser (decision-oriented); social/video must be the most accessible. docs/04.
READABILITY_FLOOR: dict[str, float] = {
    "PRESS_RELEASE": 40.0,
    "ARTICLE": 50.0,
    "SOCIAL": 50.0,
    "EXEC_SUMMARY": 30.0,
    "VIDEO_SCRIPT": 55.0,
}
_DEFAULT_FLOOR = 40.0


def factual_sentences(sentences: list[Sentence]) -> list[Sentence]:
    return [s for s in sentences if s.get("role") in FACTUAL_ROLES]


def hallucination_rate(sentences: list[Sentence]) -> float:
    """(UNSUPPORTED + CONTRADICTED) / factual sentences (docs/05 §3.1). Lower is better."""
    factual = factual_sentences(sentences)
    if not factual:
        return 0.0
    bad = sum(1 for s in factual if s.get("verdict") in HALLUCINATED_VERDICTS)
    return bad / len(factual)


def claim_precision(sentences: list[Sentence]) -> float:
    """Supported factual sentences / all factual sentences (docs/05 §1, metric 1)."""
    factual = factual_sentences(sentences)
    if not factual:
        return 1.0
    good = sum(1 for s in factual if s.get("verdict") in SUPPORTED_VERDICTS)
    return good / len(factual)


def faithfulness(sentences: list[Sentence]) -> float:
    """Mean grounding confidence over factual sentences (docs/05 §3.1, RAGAS-style).

    Reuses the TrustLayer's per-sentence confidence (the NLI + judge + overlap
    blend) rather than a second RAGAS pass — same signal, no extra LLM spend.
    """
    scored = [s["confidence"] for s in factual_sentences(sentences) if s.get("confidence") is not None]
    if not scored:
        return 0.0
    return sum(scored) / len(scored)


def evidence_link_validity(sentences: list[Sentence], valid_claim_keys: set[str]) -> float:
    """Share of factual sentences whose every cited claim key exists in the store.

    A weak proxy for docs/05 §3.3 "cited span contains the supporting text": the
    quote-in-span guarantee is enforced upstream at extraction (docs/03 §2.3), so
    here we check the generator only cited real, verified claims (no dangling refs).
    """
    factual = factual_sentences(sentences)
    if not factual:
        return 1.0
    ok = 0
    for s in factual:
        cited = s.get("claim_ids") or []
        if cited and all(c in valid_claim_keys for c in cited):
            ok += 1
    return ok / len(factual)


def _flesch(text: str, language: str) -> float:
    """Flesch reading ease. EN via textstat; HU via a sentence-length heuristic."""
    text = text.strip()
    if not text:
        return 0.0
    if language == "en":
        import textstat

        return float(textstat.flesch_reading_ease(text))
    # HU: textstat's English syllable model doesn't transfer. Approximate ease from
    # mean words-per-sentence (shorter sentences read easier) — labelled a heuristic.
    sentences = [s for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
    words = text.split()
    if not sentences or not words:
        return 0.0
    wps = len(words) / len(sentences)
    return max(0.0, min(100.0, 110.0 - 3.0 * wps))


def readability(sentences: list[Sentence], language: str, output_type: str) -> dict[str, Any]:
    """Reading ease of the output body + whether it clears the type's target band."""
    body = " ".join(s.get("text", "") for s in sentences if s.get("text"))
    ease = _flesch(body, language)
    floor = READABILITY_FLOOR.get(output_type, _DEFAULT_FLOOR)
    return {
        "reading_ease": round(ease, 1),
        "target_floor": floor,
        "band_hit": ease >= floor,
        "method": "flesch" if language == "en" else "hu_heuristic",
    }


def coverage(
    sentences: list[Sentence],
    key_fact_keys: list[str],
    match_key_fn: Any = None,
) -> dict[str, Any]:
    """Key-fact coverage (docs/05 §3.2): matched key gold facts / all key gold facts.

    ``key_fact_keys`` are the gold facts' claim keys flagged must-not-miss. A gold
    fact counts as covered if any factual sentence cites its key (or ``match_key_fn``
    returns True for a looser embedding/entity match). With no gold set, callers pass
    an empty list and this returns coverage=None (n/a) — see the intrinsic proxy below.
    """
    if not key_fact_keys:
        return {"coverage": None, "matched": [], "missed": [], "note": "no gold set"}
    cited = {c for s in factual_sentences(sentences) for c in (s.get("claim_ids") or [])}
    matched = [
        k for k in key_fact_keys if k in cited or (match_key_fn and match_key_fn(k, sentences))
    ]
    missed = [k for k in key_fact_keys if k not in matched]
    return {
        "coverage": len(matched) / len(key_fact_keys),
        "matched": matched,
        "missed": missed,
    }


def quality_score(
    faith: float,
    halluc: float,
    cov: float | None,
    evidence: float,
    readability_band_hit: bool,
) -> float:
    """Aggregate 0–100 quality, trust-weighted (docs/05 §5).

    When no gold coverage is available, its 0.20 weight is redistributed across the
    remaining signals so the score stays on 0–100 and comparable within a gold-less run.
    """
    read = 1.0 if readability_band_hit else 0.0
    if cov is None:
        total = 0.35 + 0.25 + 0.10 + 0.10
        blend = (0.35 * faith + 0.25 * (1 - halluc) + 0.10 * evidence + 0.10 * read) / total
    else:
        blend = (
            0.35 * faith
            + 0.25 * (1 - halluc)
            + 0.20 * cov
            + 0.10 * evidence
            + 0.10 * read
        )
    return round(100 * max(0.0, min(1.0, blend)), 1)


def adversarial_caught(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Share of overclaim traps the TrustLayer flagged (docs/05 §2.3, §6).

    ``results`` items: {"id", "expect", "verdict"}. A trap is caught when the actual
    verdict is in the hallucinated set (the trap was blocked/flagged, not passed).
    """
    if not results:
        return {"caught_rate": None, "caught": 0, "total": 0, "missed": []}
    caught, missed = 0, []
    for r in results:
        if r.get("verdict") in HALLUCINATED_VERDICTS:
            caught += 1
        else:
            missed.append(r.get("id"))
    return {"caught_rate": caught / len(results), "caught": caught, "total": len(results), "missed": missed}
