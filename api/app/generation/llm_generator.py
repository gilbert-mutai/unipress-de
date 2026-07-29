"""Claim-bound LLM generation (docs/03 §4) — opt-in behind settings.llm_generation.

The model is given ONLY the verified claims (as `[clm_xxx] text` lines) and must
cite claim keys on every factual sentence and introduce no new facts. Output is
schema-constrained; one self-repair pass fixes a factual sentence that cites no
claim. Every sentence is still verified downstream by the TrustLayer.
"""

from __future__ import annotations

import re

from app.core.logging import get_logger
from app.generation.fallback import ClaimInput
from app.generation.models import (
    GeneratedOutput,
    GeneratedSentence,
    OutputSpec,
    OutputType,
    SentenceRole,
)
from app.llm.gateway import LiteLLMGateway

log = get_logger("generation.llm")

_SYSTEM = (
    "You are a science communications writer. Write the requested output using ONLY "
    "the provided claims. Every factual sentence MUST cite one or more claim IDs from "
    "the list and MUST NOT introduce facts, numbers, or names not present in the claims. "
    "Mark hooks/connectives as role RHETORICAL or TRANSITION (no claim IDs). "
    'Return JSON: {"title":str,"sentences":[{"text":str,"role":'
    '"FACT|INTERPRETATION|RHETORICAL|TRANSITION","claim_ids":[str],"section":str}]}.'
)

_VIDEO_SYSTEM = (
    "You are a science-video scriptwriter. Write a ≤60-second script as ordered SCENES "
    "(hook, context, finding, meaning, cta) using ONLY the provided claims. For each scene "
    "return: text (the spoken narration; factual scenes MUST cite claim IDs and add no new "
    "facts/numbers), on_screen (a very short on-screen caption), visual (a visual suggestion), "
    "timecode (e.g. '0:20–0:45'), section (the scene name), role "
    "(FACT for narrated claims; RHETORICAL for the hook/cta). "
    'Return JSON: {"title":str,"sentences":[{"text":str,"role":str,"claim_ids":[str],'
    '"section":str,"timecode":str,"on_screen":str,"visual":str}]}.'
)


def _prompt(spec: OutputSpec, claims: list[ClaimInput], language: str) -> str:
    claim_lines = "\n".join(f"[{c.key}] ({c.claim_type}) {c.text}" for c in claims)
    return (
        f"Output type: {spec.output_type}\nLanguage: {language}\nTone: {spec.tone}\n"
        f"Length: {spec.length_target}\nStructure (in order): {', '.join(spec.structure)}\n"
        f"Must include: {', '.join(spec.must_include)}\n"
        f"Must avoid: {', '.join(spec.must_avoid)}\n\nCLAIMS:\n{claim_lines}"
    )


# Claim ids belong in the claim_ids field, not in the prose — but the model
# occasionally trails them into the sentence itself ("…consistency (clm_003,
# clm_005)."), most often when writing Hungarian. Left in, they are published
# text a reviewer would see, and the numeric check reads the digits out of
# "clm_003" as if they were quantities. Strip them defensively; claim_ids is
# still the authoritative citation.
_INLINE_CITATION = re.compile(
    r"""[\s]*[(\[]\s*                 # opening bracket
        clm[_-]?\d+                   # first id
        (?:\s*[,;/]\s*clm[_-]?\d+)*   # any further ids
        \s*[)\]]""",
    re.IGNORECASE | re.VERBOSE,
)


def _strip_inline_citations(text: str) -> str:
    cleaned = _INLINE_CITATION.sub("", text)
    # A trailing citation often sat before the full stop: "…text (clm_003)."
    return re.sub(r"\s+([.!?])", r"\1", cleaned).strip()


def _parse(payload: dict, spec: OutputSpec, language: str, title_hint: str) -> GeneratedOutput:
    sentences: list[GeneratedSentence] = []
    for raw in payload.get("sentences", []):
        text = _strip_inline_citations((raw.get("text") or "").strip())
        if not text:
            continue
        try:
            role = SentenceRole(raw.get("role", "FACT"))
        except ValueError:
            role = SentenceRole.FACT
        sentences.append(
            GeneratedSentence(
                text=text,
                role=role,
                claim_ids=[str(c) for c in raw.get("claim_ids", [])],
                section=raw.get("section"),
                timecode=raw.get("timecode"),
                on_screen=raw.get("on_screen"),
                visual=raw.get("visual"),
            )
        )
    return GeneratedOutput(
        output_type=spec.output_type,
        language=language,
        title=(payload.get("title") or title_hint).strip(),
        sentences=sentences,
    )


def _needs_repair(output: GeneratedOutput) -> bool:
    return any(s.is_factual and not s.claim_ids for s in output.sentences)


def generate_llm(
    spec: OutputSpec, claims: list[ClaimInput], language: str, title_hint: str
) -> GeneratedOutput:
    from app.core.settings import get_settings

    gateway = LiteLLMGateway(model=get_settings().llm_generation_model)
    system = _VIDEO_SYSTEM if spec.output_type == OutputType.VIDEO_SCRIPT else _SYSTEM
    user = _prompt(spec, claims, language)
    output = _parse(gateway.complete_json(system, user), spec, language, title_hint)

    if _needs_repair(output):  # one bounded self-repair pass
        log.info("generation.self_repair")
        repair = user + (
            "\n\nEVERY factual sentence must include at least one claim_id, or be "
            "marked RHETORICAL/TRANSITION. Fix and return the same JSON."
        )
        output = _parse(gateway.complete_json(_SYSTEM, repair), spec, language, title_hint)
    return output
