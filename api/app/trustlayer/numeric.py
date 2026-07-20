"""Numeric verification — the single highest-value trust check (docs/03 §5.4).

Numbers are the #1 hallucination risk, so every number in a generated sentence
must be corroborated by a number in the cited source span (within a small
rounding tolerance). A number with no match => numeric mismatch => hard penalty.
"""

from __future__ import annotations

import re

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_REL_TOL = 0.02  # 2% tolerance absorbs honest rounding ("nearly 90%" vs 88.8)


def numbers(text: str) -> list[float]:
    out: list[float] = []
    for m in _NUMBER.findall(text):
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            continue
    return out


def _matches(value: float, candidates: list[float]) -> bool:
    return any(abs(value - c) <= max(_REL_TOL * abs(c), 1e-9) for c in candidates)


def numeric_mismatch(sentence: str, premise: str) -> bool:
    """True if the sentence contains a number not corroborated by the premise."""
    sentence_nums = numbers(sentence)
    if not sentence_nums:
        return False
    premise_nums = numbers(premise)
    return any(not _matches(n, premise_nums) for n in sentence_nums)
