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

# Digits that begin a token, so identifiers are not mined for quantities: the
# "003" in a leaked "clm_003" citation is not a number anyone claimed, and
# reading it as one made the check hard-fail correct sentences.
_NUMBER = re.compile(r"(?<![A-Za-z0-9_])\d[\d.,]*")
_REL_TOL = 0.02  # 2% tolerance absorbs honest rounding ("nearly 90%" vs 88.8)
_THOUSANDS = re.compile(r"\d{1,3}(?:,\d{3})+")  # 1,234 / 12,345,678
_DECIMAL_COMMA = re.compile(r"\d+,\d{1,3}")  # 88,8 / 0,05

# Small spelled-out numbers, EN + HU. Papers write "nine networks" while a
# generated sentence — especially a translated one — writes "9". Both sides are
# normalised so the two forms compare equal.
_WORD_NUMBERS = {
    # English
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "hundred": 100,
    "thousand": 1000,
    "million": 1000000,
    "billion": 1000000000,
    # Hungarian
    "nulla": 0,
    "egy": 1,
    "kettő": 2,
    "két": 2,
    "három": 3,
    "négy": 4,
    "öt": 5,
    "hat": 6,
    "hét": 7,
    "nyolc": 8,
    "kilenc": 9,
    "tíz": 10,
    "tizenegy": 11,
    "tizenkettő": 12,
    "húsz": 20,
    "harminc": 30,
    "negyven": 40,
    "ötven": 50,
    "száz": 100,
    "ezer": 1000,
    "millió": 1000000,
    "milliárd": 1000000000,
}
_WORD_RE = re.compile(r"\b(" + "|".join(sorted(_WORD_NUMBERS, key=len, reverse=True)) + r")\b")


def _with_word_numbers(text: str) -> str:
    """Rewrite spelled-out numbers as digits so both forms compare equal."""
    return _WORD_RE.sub(lambda m: str(_WORD_NUMBERS[m.group(1).lower()]), text.lower())


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
    return [v for m in _NUMBER.findall(_with_word_numbers(text)) if (v := _variants(m))]


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
