"""Generation orchestration: claims -> claim-bound output -> TrustLayer -> persist."""

from __future__ import annotations

from app.core.db import session_scope
from app.core.logging import get_logger
from app.core.settings import get_settings
from app.db_models import Claim as ClaimRow
from app.db_models import Document, OutputRecord, SentenceRecord
from app.generation.fallback import ClaimInput, generate_fallback
from app.generation.models import GeneratedOutput, OutputSpec, OutputType
from app.generation.specs import get_spec
from app.trustlayer.coverage import coverage_report
from app.trustlayer.verify import ClaimEvidence, verify_output

log = get_logger("generation.service")


def _load_claims(document_id: str) -> tuple[list[ClaimInput], dict[str, ClaimEvidence], str]:
    with session_scope() as s:
        doc = s.get(Document, document_id)
        if doc is None:
            raise ValueError(f"document {document_id} not found")
        title_hint = doc.filename
        rows = s.query(ClaimRow).filter(ClaimRow.document_id == document_id).all()
        claims = [
            ClaimInput(key=r.key, text=r.text, claim_type=r.claim_type, importance=r.importance)
            for r in rows
        ]
        evidence = {r.key: ClaimEvidence(key=r.key, quote=r.quote) for r in rows}
    return claims, evidence, title_hint


def _generate(
    spec: OutputSpec, claims: list[ClaimInput], language: str, title_hint: str
) -> GeneratedOutput:
    settings = get_settings()
    if settings.llm_generation and settings.openai_api_key:
        from app.generation.llm_generator import generate_llm

        log.info("generate.llm", model=settings.llm_generation_model)
        return generate_llm(spec, claims, language, title_hint)
    return generate_fallback(spec, claims, language, title_hint)


def generate_output(document_id: str, output_type: str, language: str) -> str:
    """Generate + verify + persist one output. Returns the output record id."""
    spec = get_spec(OutputType(output_type))
    claims, evidence, title_hint = _load_claims(document_id)

    output = _generate(spec, claims, language, title_hint)
    verify_output(output, evidence)  # TrustLayer: verdict + confidence per sentence
    coverage = coverage_report(claims, output)  # document-level: omissions, dropped caveats

    with session_scope() as s:
        record = OutputRecord(
            document_id=document_id,
            output_type=output.output_type.value,
            language=language,
            title=output.title,
            status="done",
            coverage=coverage,
        )
        s.add(record)
        s.flush()
        for i, sent in enumerate(output.sentences):
            s.add(
                SentenceRecord(
                    output_id=record.id,
                    order_index=i,
                    text=sent.text,
                    role=sent.role.value,
                    claim_ids=sent.claim_ids or None,
                    section=sent.section,
                    timecode=sent.timecode,
                    on_screen=sent.on_screen,
                    visual=sent.visual,
                    verdict=sent.verdict.value if sent.verdict else None,
                    confidence=sent.confidence,
                    rationale=sent.rationale,
                )
            )
        output_id = record.id
    log.info(
        "generated",
        document_id=document_id,
        output_type=output_type,
        language=language,
        sentences=len(output.sentences),
    )
    return output_id
