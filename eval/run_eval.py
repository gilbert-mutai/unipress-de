#!/usr/bin/env python3
"""UniPress DE — evaluation harness (docs/05 §8).

Runs the real pipeline end-to-end in-process (parse → chunk → extract → embed →
generate → TrustLayer) on the sample papers, computes the docs/05 metrics per
(paper × output type × language), and writes a timestamped JSON + Markdown report
to ``eval/reports/``. By default it uses the deterministic fallback generator and
throwaway infra (in-memory SQLite, hashing embedder, in-memory vector store) so a
run needs no services, no API key, and is fully reproducible — the shape the CI
eval-gate depends on.

    python eval/run_eval.py                      # all EN research papers, all output types
    python eval/run_eval.py --papers pap_smear_screening --outputs PRESS_RELEASE
    python eval/run_eval.py --label baseline      # name the report dir

Gold-based coverage + adversarial-trap metrics activate automatically when a
frozen gold file exists at ``eval/gold/<paper_id>.yaml`` (see eval/README.md).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))  # sibling metrics.py
sys.path.insert(0, str(REPO / "api"))  # the app package

import metrics  # noqa: E402

DEFAULT_OUTPUTS = ["PRESS_RELEASE", "ARTICLE", "SOCIAL", "EXEC_SUMMARY", "VIDEO_SCRIPT"]
MANIFEST = REPO / "data" / "manifest.yaml"
SAMPLES = REPO / "sample_files_for_PR"
GOLD_DIR = ROOT / "gold"
REPORTS_DIR = ROOT / "reports"


# --------------------------------------------------------------------------- infra


def _setup_infra() -> Any:
    """Point the app at throwaway, service-free infra (mirrors tests/conftest.py)."""
    import tempfile

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import app.db_models  # noqa: F401 - register tables
    from app.core import db
    from app.core.settings import get_settings

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    db.Base.metadata.create_all(engine)
    db.SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    db._engine = engine

    settings = get_settings()
    settings.storage_root = tempfile.mkdtemp(prefix="unipress-eval-")
    settings.embed_backend = "hashing"
    settings.vector_backend = "memory"

    from app.retrieval import embedder as _emb
    from app.retrieval import service as _rsvc

    _emb.reset_embedder()
    _rsvc.reset_vector_store()
    return db


def _ingest(db: Any, pdf: Path) -> str:
    from app.adapters.stubs import LocalStorage
    from app.claims.service import extract_stage
    from app.db_models import Document
    from app.ingestion.service import chunk_stage, parse_stage
    from app.retrieval.service import embed_stage

    data = pdf.read_bytes()
    with db.session_scope() as s:
        doc = Document(filename=pdf.name, content_key="", status="pending")
        s.add(doc)
        s.flush()
        doc_id = doc.id
        doc.content_key = f"{doc_id}/source.pdf"
    LocalStorage().put(f"{doc_id}/source.pdf", data)

    parse_stage(doc_id)
    chunk_stage(doc_id)
    extract_stage(doc_id)
    embed_stage(doc_id)
    return doc_id


def _generate(db: Any, doc_id: str, output_type: str, language: str) -> dict[str, Any]:
    from sqlalchemy import select

    from app.db_models import Claim, OutputRecord
    from app.generation.service import generate_output

    output_id = generate_output(doc_id, output_type, language)
    with db.session_scope() as s:
        rec = s.get(OutputRecord, output_id)
        sentences = [
            {
                "text": x.text,
                "role": x.role,
                "claim_ids": x.claim_ids or [],
                "verdict": x.verdict,
                "confidence": x.confidence,
                "section": x.section,
            }
            for x in sorted(rec.sentences, key=lambda z: z.order_index)
        ]
        claim_keys = {
            c.key for c in s.scalars(select(Claim).where(Claim.document_id == doc_id))
        }
    return {"sentences": sentences, "claim_keys": claim_keys}


# --------------------------------------------------------------------------- gold


def _load_gold(paper_id: str) -> dict[str, Any] | None:
    path = GOLD_DIR / f"{paper_id}.yaml"
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text()) or {}


# --------------------------------------------------------------------------- eval


def evaluate(sentences: list[dict], claim_keys: set[str], output_type: str, language: str,
             gold: dict | None) -> dict[str, Any]:
    key_facts = list((gold or {}).get("key_fact_claim_keys", []))
    halluc = metrics.hallucination_rate(sentences)
    faith = metrics.faithfulness(sentences)
    precision = metrics.claim_precision(sentences)
    evidence = metrics.evidence_link_validity(sentences, claim_keys)
    read = metrics.readability(sentences, language, output_type)
    cov = metrics.coverage(sentences, key_facts)
    quality = metrics.quality_score(
        faith, halluc, cov["coverage"], evidence, read["band_hit"]
    )
    factual = metrics.factual_sentences(sentences)
    return {
        "sentences_total": len(sentences),
        "sentences_factual": len(factual),
        "hallucination_rate": round(halluc, 4),
        "faithfulness": round(faith, 4),
        "claim_precision": round(precision, 4),
        "evidence_link_validity": round(evidence, 4),
        "readability": read,
        "coverage": cov,
        "quality_score": quality,
    }


def _aggregate(rows: list[dict]) -> dict[str, Any]:
    """Mean of the headline metrics across all (paper × output) rows."""
    if not rows:
        return {}
    n = len(rows)
    return {
        "runs": n,
        "hallucination_rate": round(sum(r["metrics"]["hallucination_rate"] for r in rows) / n, 4),
        "faithfulness": round(sum(r["metrics"]["faithfulness"] for r in rows) / n, 4),
        "claim_precision": round(sum(r["metrics"]["claim_precision"] for r in rows) / n, 4),
        "evidence_link_validity": round(
            sum(r["metrics"]["evidence_link_validity"] for r in rows) / n, 4
        ),
        "readability_band_hit_rate": round(
            sum(1 for r in rows if r["metrics"]["readability"]["band_hit"]) / n, 4
        ),
        "quality_score": round(sum(r["metrics"]["quality_score"] for r in rows) / n, 1),
    }


# --------------------------------------------------------------------------- report


TARGETS = {  # docs/05 §6 MVP acceptance bars
    "hallucination_rate": ("<=", 0.05),
    "faithfulness": (">=", 0.90),
    "evidence_link_validity": (">=", 0.95),
}


def _target_check(agg: dict[str, Any]) -> list[dict[str, Any]]:
    checks = []
    for metric, (op, target) in TARGETS.items():
        val = agg.get(metric)
        if val is None:
            continue
        met = val <= target if op == "<=" else val >= target
        checks.append({"metric": metric, "op": op, "target": target, "value": val, "met": met})
    return checks


def _write_report(report: dict[str, Any], label: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"{stamp}-{label}" if label else stamp
    out = REPORTS_DIR / name
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=2, default=str))
    (out / "report.md").write_text(_markdown(report))
    return out


def _markdown(report: dict[str, Any]) -> str:
    agg = report["aggregate"]
    lines = [
        f"# UniPress DE — eval report `{report['label'] or report['run_at']}`",
        "",
        f"- Run at: {report['run_at']}",
        f"- Generator: {report['generator']}  ·  Papers: {len(report['papers'])}  "
        f"·  Runs: {agg.get('runs', 0)}",
        "",
        "## Headline (mean across runs)",
        "",
        "| Metric | Value | Target | Met |",
        "|---|---|---|---|",
    ]
    checks = {c["metric"]: c for c in report["target_checks"]}
    for metric in ["hallucination_rate", "faithfulness", "claim_precision",
                   "evidence_link_validity", "readability_band_hit_rate", "quality_score"]:
        val = agg.get(metric)
        c = checks.get(metric)
        tgt = f"{c['op']} {c['target']}" if c else "—"
        met = "✅" if c and c["met"] else ("❌" if c else "—")
        lines.append(f"| {metric} | {val} | {tgt} | {met} |")
    lines += ["", "## Per output", "", "| Paper | Output | Lang | Halluc | Faith | Precision | Quality |",
              "|---|---|---|---|---|---|---|"]
    for r in report["rows"]:
        m = r["metrics"]
        lines.append(
            f"| {r['paper']} | {r['output_type']} | {r['language']} | "
            f"{m['hallucination_rate']} | {m['faithfulness']} | {m['claim_precision']} | "
            f"{m['quality_score']} |"
        )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- main


def _select_papers(requested: list[str] | None) -> list[dict[str, Any]]:
    manifest = yaml.safe_load(MANIFEST.read_text())
    docs = manifest["documents"]
    papers = []
    for d in docs:
        if requested and d["id"] not in requested:
            continue
        if not requested and d.get("genre") != "research_paper":
            continue  # default: the claim-dense research papers (not the HU curricula)
        pdf = SAMPLES / d["file"]
        if not pdf.exists():
            print(f"  ! skipping {d['id']}: PDF not found at {pdf}", file=sys.stderr)
            continue
        papers.append({"id": d["id"], "pdf": pdf, "language": d.get("language", "en")})
    return papers


def main() -> int:
    ap = argparse.ArgumentParser(description="UniPress DE evaluation harness")
    ap.add_argument("--papers", nargs="*", help="manifest ids (default: all research papers)")
    ap.add_argument("--outputs", nargs="*", default=DEFAULT_OUTPUTS, help="output types")
    ap.add_argument("--label", default="", help="report dir label")
    ap.add_argument("--fail-on-target-miss", action="store_true",
                    help="exit non-zero if a headline target is missed (CI eval-gate)")
    args = ap.parse_args()

    papers = _select_papers(args.papers)
    if not papers:
        print("No papers to evaluate (are the sample PDFs present?)", file=sys.stderr)
        return 2

    db = _setup_infra()
    rows: list[dict[str, Any]] = []
    for p in papers:
        print(f"→ {p['id']} ({p['language']})")
        doc_id = _ingest(db, p["pdf"])
        gold = _load_gold(p["id"])
        for output_type in args.outputs:
            run = _generate(db, doc_id, output_type, p["language"])
            m = evaluate(run["sentences"], run["claim_keys"], output_type, p["language"], gold)
            rows.append({"paper": p["id"], "output_type": output_type,
                         "language": p["language"], "metrics": m})
            print(f"    {output_type:14s} halluc={m['hallucination_rate']:.3f} "
                  f"faith={m['faithfulness']:.3f} quality={m['quality_score']}")

    agg = _aggregate(rows)
    checks = _target_check(agg)
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "generator": "deterministic-fallback",
        "papers": [p["id"] for p in papers],
        "rows": rows,
        "aggregate": agg,
        "target_checks": checks,
    }
    out = _write_report(report, args.label)
    print(f"\nReport → {out.relative_to(REPO)}")
    print(f"Aggregate: halluc={agg['hallucination_rate']} faith={agg['faithfulness']} "
          f"quality={agg['quality_score']}")

    missed = [c for c in checks if not c["met"]]
    if missed:
        print("Targets missed: " + ", ".join(c["metric"] for c in missed), file=sys.stderr)
    if args.fail_on_target_miss and missed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
