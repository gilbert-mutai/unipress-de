"""Numeric verification — the single highest-value trust check (docs/03 §5.4).

Numbers are the #1 hallucination risk, so every number in a generated sentence
must be corroborated by a number in the cited source span (within a small
rounding tolerance). A number with no match => numeric mismatch => hard penalty.

Parsing is locale-aware because the system is bilingual: Hungarian writes
decimals with a comma ("88,8%") while the English source papers use a point
("88.8%"). Reading every comma as a thousands separator turned 88,8 into 888 and
fired CONTRADICTED on correct Hungarian sentences. Where a token is genuinely
ambiguous ("1,234" is 1234 in English, 1.234 in Hungarian) both readings are kept,
and a mismatch is reported only when *no* reading of the sentence's number matches
*any* reading in the premise — this check must never accuse a faithful sentence
over a punctuation convention.
"""

from __future__ import annotations

import re

_NUMBER = re.compile(r"\d[\d.,]*")
_REL_TOL = 0.02  # 2% tolerance absorbs honest rounding ("nearly 90%" vs 88.8)
_THOUSANDS = re.compile(r"\d{1,3}(?:,\d{3})+")  # 1,234 / 12,345,678
_DECIMAL_COMMA = re.compile(r"\d+,\d{1,3}")  # 88,8 / 0,05


def _variants(token: str) -> list[float]:
    """Every plausible value for one numeric token, across EN and HU conventions."""
    t = token.strip(".,")
    if not t:
        return []
    candidates: list[str] = []

    if "," in t and "." in t:
        # Whichever separator comes last is the decimal one.
        if t.rfind(",") > t.rfind("."):
            candidates.append(t.replace(".", "").replace(",", "."))
        else:
            candidates.append(t.replace(",", ""))
    elif "," in t:
        if _THOUSANDS.fullmatch(t):
            candidates.append(t.replace(",", ""))  # unambiguous grouping
        elif _DECIMAL_COMMA.fullmatch(t):
            candidates.append(t.replace(",", "."))  # unambiguous decimal comma
        else:
            candidates.append(t.replace(",", ""))
            candidates.append(t.replace(",", "."))
    else:
        candidates.append(t)

    out: list[float] = []
    for c in candidates:
        try:
            out.append(float(c))
        except ValueError:
            continue
    return out


def numbers(text: str) -> list[float]:
    """Primary reading of each number in `text` (used for Tier-2 judge gating)."""
    return [v[0] for m in _NUMBER.findall(text) if (v := _variants(m))]


def _all_variants(text: str) -> list[list[float]]:
    """Per-token candidate readings, for tolerant comparison."""
    return [v for m in _NUMBER.findall(text) if (v := _variants(m))]


def _matches(values: list[float], candidates: list[float]) -> bool:
    return any(
        abs(value - c) <= max(_REL_TOL * abs(c), 1e-9) for value in values for c in candidates
    )


def numeric_mismatch(sentence: str, premise: str) -> bool:
    """True if the sentence contains a number not corroborated by the premise."""
    sentence_nums = _all_variants(sentence)
    if not sentence_nums:
        return False
    premise_nums = [v for variants in _all_variants(premise) for v in variants]
    return any(not _matches(values, premise_nums) for values in sentence_nums)
