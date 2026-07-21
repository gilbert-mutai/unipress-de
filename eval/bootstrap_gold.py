#!/usr/bin/env python3
"""Bootstrap candidate gold files for human verification (docs/05 §2.2).

The extractor does the heavy lifting; a human then verifies/corrects/marks key facts.
This script ingests each research paper, dumps every extracted claim, proposes an
initial set of key facts (top findings/quantitative by importance), and auto-generates
numeric overclaim traps — each **self-validated** by running it through the TrustLayer
so only traps the system actually catches are proposed. Output goes to
``eval/gold/<paper_id>.candidate.yaml`` (the harness ignores ``.candidate`` files;
rename to ``<paper_id>.yaml`` once verified to freeze it as gold).

    python eval/bootstrap_gold.py                      # all research papers
    python eval/bootstrap_gold.py --papers pap_smear_screening
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / "api"))

from run_eval import _ingest, _select_papers, _setup_infra  # noqa: E402

GOLD_DIR = ROOT / "gold"
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_KEY_FACT_TYPES = {"FINDING", "QUANTITATIVE"}
_MAX_KEY_FACTS = 6
_MAX_TRAPS = 5


def _claims(db: Any, doc_id: str) -> list[dict[str, Any]]:
    from app.db_models import Claim

    with db.session_scope() as s:
        rows = s.query(Claim).filter(Claim.document_id == doc_id).all()
        return [
            {"key": r.key, "text": r.text, "type": r.claim_type, "page": r.page,
             "importance": round(r.importance, 3), "numeric": r.numeric, "quote": r.quote}
            for r in rows
        ]


def _perturb_number(text: str) -> str | None:
    """Change the first number in a claim to a clearly-wrong-but-plausible value."""
    m = _NUMBER.search(text)
    if not m:
        return None
    raw = m.group(0)
    try:
        value = float(raw.replace(",", ""))
    except ValueError:
        return None
    # Shift the leading digit so the magnitude reads plausible but the value is wrong.
    bumped = value + 10 if value < 90 else value * 1.5
    new = f"{bumped:.1f}".rstrip("0").rstrip(".") if "." in raw else str(int(bumped))
    return text[: m.start()] + new + text[m.end():]


def _verdict_for(perturbed: str, claim: dict[str, Any]) -> str:
    """Run a single perturbed sentence through the TrustLayer against its source claim."""
    from app.generation.models import GeneratedOutput, GeneratedSentence, OutputType, SentenceRole
    from app.trustlayer.verify import ClaimEvidence, verify_output

    output = GeneratedOutput(
        output_type=OutputType.PRESS_RELEASE,
        language="en",
        title="adversarial probe",
        sentences=[GeneratedSentence(text=perturbed, role=SentenceRole.FACT,
                                     claim_ids=[claim["key"]])],
    )
    verify_output(output, {claim["key"]: ClaimEvidence(key=claim["key"], quote=claim["quote"])})
    return output.sentences[0].verdict.value if output.sentences[0].verdict else "UNKNOWN"


def _build_traps(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    traps = []
    for c in sorted(claims, key=lambda x: x["importance"], reverse=True):
        if len(traps) >= _MAX_TRAPS:
            break
        if not c["numeric"]:
            continue
        perturbed = _perturb_number(c["text"])
        if not perturbed or perturbed == c["text"]:
            continue
        verdict = _verdict_for(perturbed, c)
        if verdict not in {"CONTRADICTED", "UNSUPPORTED"}:
            continue  # keep only traps the TrustLayer actually catches
        traps.append({
            "id": f"adv_{len(traps) + 1:03d}",
            "against_claim": c["key"],
            "perturbed": perturbed,
            "expect": "CONTRADICTED",
            "_verified_verdict": verdict,  # what the TrustLayer returned at bootstrap
        })
    return traps


def bootstrap(paper: dict[str, Any], db: Any) -> dict[str, Any]:
    doc_id = _ingest(db, paper["filename"], paper["data"])
    claims = _claims(db, doc_id)
    ranked = sorted(claims, key=lambda c: c["importance"], reverse=True)
    key_facts = [c["key"] for c in ranked if c["type"] in _KEY_FACT_TYPES][:_MAX_KEY_FACTS]
    traps = _build_traps(claims)
    return {
        "paper_id": paper["id"],
        "_status": "CANDIDATE — human must verify/correct/mark key facts before freezing",
        "key_fact_claim_keys": key_facts,
        "adversarial": traps,
        "_all_claims": [  # reference for the human reviewer (drop before freezing)
            {k: c[k] for k in ("key", "type", "page", "importance", "numeric", "text")}
            for c in ranked
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Bootstrap candidate gold files")
    ap.add_argument("--papers", nargs="*", help="manifest ids (default: all research papers)")
    args = ap.parse_args()

    papers = _select_papers(args.papers, synthetic=False)
    if not papers:
        print("No papers found (are the sample PDFs present?)", file=sys.stderr)
        return 2

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    db = _setup_infra()
    for paper in papers:
        print(f"→ {paper['id']}")
        candidate = bootstrap(paper, db)
        out = GOLD_DIR / f"{paper['id']}.candidate.yaml"
        out.write_text(yaml.safe_dump(candidate, sort_keys=False, allow_unicode=True, width=100))
        print(f"    {len(candidate['key_fact_claim_keys'])} key-fact candidates, "
              f"{len(candidate['adversarial'])} self-validated traps → {out.relative_to(REPO)}")
    print("\nReview each .candidate.yaml, correct it, then rename to <paper_id>.yaml to freeze.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
