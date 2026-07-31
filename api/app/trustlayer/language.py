"""Which of the two supported languages a piece of text is in.

Only needed to decide whether a lexical comparison between a generated sentence
and its cited quote is meaningful at all (see scorer.confidence). The corpus is
Hungarian and English, so a cheap script-and-function-word test is enough and
costs nothing per sentence — `documents.language` exists in the schema but has
never been populated, and adding a detection dependency for a binary decision
would be disproportionate.
"""

from __future__ import annotations

import re

# Vowels with Hungarian-specific diacritics. The double-acute ő/ű are unique to
# Hungarian among the languages in play; the rest are strong signals together.
_HU_CHARS = re.compile(r"[őűáéíóöúü]", re.IGNORECASE)

# High-frequency Hungarian function words that do not occur in English prose.
_HU_WORDS = frozenset(
    """
    és hogy nem egy van meg már csak ez az ezt azt ami amely aki volt lehet így
    több mint után előtt között vagy sem is a-ban ban ben nál nél val vel ról ről
    szerint során illetve valamint azonban tehát míg amikor mivel
    """.split()
)
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def looks_hungarian(text: str) -> bool:
    """True if `text` reads as Hungarian rather than English."""
    if not text:
        return False
    words = [w.lower() for w in _WORD.findall(text)]
    if not words:
        return False
    hu_words = sum(1 for w in words if w in _HU_WORDS)
    accents = len(_HU_CHARS.findall(text))
    # Either signal alone is enough on real sentences: English quotes from these
    # papers carry no Hungarian diacritics and none of these function words.
    return (hu_words / len(words)) >= 0.08 or accents >= 3


def same_language(a: str, b: str) -> bool:
    """True if both texts appear to be in the same one of the two languages."""
    return looks_hungarian(a) == looks_hungarian(b)
