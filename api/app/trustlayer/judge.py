"""Tier-2 LLM judge (docs/03 §5.2) — nuanced, explainable adjudication.

Opt-in (settings.llm_judge + a key). Called only for sentences Tier-1 can't
settle cheaply (borderline entailment or any numeric statement), so most
sentences never reach a paid call. Returns a supported-fraction (fed into the
confidence blend) and a human-readable rationale (shown in the review UI).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger
from app.core.settings import get_settings
from app.llm.gateway import LiteLLMGateway

log = get_logger("trustlayer.judge")

_SYSTEM = (
    "You verify whether a STATEMENT is supported by a SOURCE excerpt from a research "
    "paper. Decide one label: 'supported' (fully entailed), 'interpretation' (reasonable "
    "inference), 'unsupported' (not in source), or 'contradicted' (source says otherwise). "
    "For any number, verify the exact value against the source. Return JSON: "
    '{"label":..,"supported_fraction":0..1,"rationale":str,"offending_text":str|null}.'
)


@dataclass
class JudgeResult:
    label: str
    supported_fraction: float
    rationale: str


class LLMJudge:
    def __init__(self) -> None:
        self.gateway = LiteLLMGateway(model=get_settings().llm_judge_model)

    def judge(self, source: str, statement: str) -> JudgeResult:
        payload = self.gateway.complete_json(
            _SYSTEM, f"SOURCE:\n{source}\n\nSTATEMENT:\n{statement}"
        )
        try:
            fraction = float(payload.get("supported_fraction", 0.0) or 0.0)
        except (TypeError, ValueError):
            fraction = 0.0
        return JudgeResult(
            label=str(payload.get("label", "unsupported")).lower(),
            supported_fraction=max(0.0, min(1.0, fraction)),
            rationale=str(payload.get("rationale", "")),
        )


_judge: LLMJudge | None = None


def get_judge() -> LLMJudge:
    global _judge
    if _judge is None:
        _judge = LLMJudge()
    return _judge


def judge_enabled() -> bool:
    s = get_settings()
    return bool(s.llm_judge and s.openai_api_key)
