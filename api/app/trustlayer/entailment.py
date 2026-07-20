"""Entailment (Tier-1) behind a port.

`classify()` returns 3-way NLI scores (entail / neutral / contradict).
`LexicalEntailment` is a dependency-free proxy (word overlap; it cannot detect
contradiction, so `contradict` is always 0) — enough to run and test the
TrustLayer with no model. The real `DebertaNLI` backend (app/trustlayer/nli.py)
implements the same port and is selected via settings.nli_backend="nli".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

_TOKEN = re.compile(r"\w+", re.UNICODE)
_STOPWORDS = {
    "the",
    "a",
    "an",
    "of",
    "to",
    "in",
    "on",
    "and",
    "or",
    "for",
    "with",
    "by",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "that",
    "this",
    "it",
    "as",
    "at",
    "from",
    "which",
    "their",
    "its",
    "we",
    "our",
    "than",
    "more",
    "less",
}


def content_tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1]


@dataclass
class NLIScores:
    entail: float
    neutral: float
    contradict: float


@runtime_checkable
class Entailment(Protocol):
    def classify(self, premise: str, hypothesis: str) -> NLIScores: ...

    def entail_prob(self, premise: str, hypothesis: str) -> float: ...


class LexicalEntailment:
    """Proxy: share of hypothesis content words present in the premise (no contradiction signal)."""

    def classify(self, premise: str, hypothesis: str) -> NLIScores:
        e = self.entail_prob(premise, hypothesis)
        return NLIScores(entail=e, neutral=1.0 - e, contradict=0.0)

    def entail_prob(self, premise: str, hypothesis: str) -> float:
        hyp = content_tokens(hypothesis)
        if not hyp:
            return 1.0
        prem = set(content_tokens(premise))
        return sum(1 for t in hyp if t in prem) / len(hyp)


_entailment: Entailment | None = None


def get_entailment() -> Entailment:
    global _entailment
    ent = _entailment
    if ent is None:
        from app.core.settings import get_settings

        if get_settings().nli_backend == "nli":
            from app.trustlayer.nli import DebertaNLI

            ent = DebertaNLI()
        else:
            ent = LexicalEntailment()
        _entailment = ent
    return ent


def reset_entailment() -> None:
    global _entailment
    _entailment = None
