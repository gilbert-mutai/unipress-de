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


def _ingest(db: Any, filename: str, data: bytes) -> str:
    from app.adapters.stubs import LocalStorage
    from app.claims.service import extract_stage
    from app.db_models import Document
    from app.ingestion.service import chunk_stage, parse_stage
    from app.retrieval.service import embed_stage

    with db.session_scope() as s:
        doc = Document(filename=filename, content_key="", status="pending")
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


# A committed-free, service-free fixture paper for the CI eval-gate: the real sample
# PDFs are gitignored (licensing + size), so CI runs the harness on this synthetic,
# claim-dense abstract built in-memory with PyMuPDF — the "small fixed set" of docs/05 §8.
_SYNTHETIC_TEXT = (
    "Abstract\n\n"
    "We present a novel screening method for early cancer detection from routine imaging. "
    "The system achieved 88.8% accuracy across 339 clinical samples in a retrospective study. "
    "Our approach reduced false negatives by 42% compared with the manual baseline. "
    "The model processed over 12 million individual cell predictions during evaluation. "
    "These results suggest the method could assist clinicians in high-volume screening settings. "
    "However, the approach is limited to born-digital images and has not been validated prospectively.\n\n"
    "1. Introduction\n\n"
    "Cervical cancer screening remains labour-intensive and error-prone. "
    "Prior automated methods report accuracy between 70% and 85% but generalise poorly. "
    "We address this gap with a claim-bound deep learning pipeline evaluated on a curated cohort."
)


def _synthetic_pdf() -> bytes:
    import fitz  # PyMuPDF

    doc = fitz.open()
    page = doc.new_page()
    page.insert_textbox(fitz.Rect(56, 56, 540, 760), _SYNTHETIC_TEXT, fontsize=11)
    return doc.tobytes()


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


def run_adversarial(db: Any, doc_id: str, gold: dict | None) -> dict[str, Any] | None:
    """Run each gold overclaim trap through the TrustLayer; report the caught rate.

    Proves the system *catches* problems, not just passes clean text (docs/05 §2.3, §6).
    Each trap's perturbed sentence is verified against its source claim; a trap is caught
    when the verdict is UNSUPPORTED/CONTRADICTED.
    """
    traps = (gold or {}).get("adversarial") or []
    if not traps:
        return None

    from sqlalchemy import select

    from app.db_models import Claim
    from app.generation.models import (
        GeneratedOutput,
        GeneratedSentence,
        OutputType,
        SentenceRole,
    )
    from app.trustlayer.verify import ClaimEvidence, verify_output

    with db.session_scope() as s:
        quotes = {c.key: c.quote for c in s.scalars(select(Claim).where(Claim.document_id == doc_id))}

    results = []
    for trap in traps:
        key = trap["against_claim"]
        if key not in quotes:
            continue
        output = GeneratedOutput(
            output_type=OutputType.PRESS_RELEASE, language="en", title="adversarial",
            sentences=[GeneratedSentence(text=trap["perturbed"], role=SentenceRole.FACT,
                                         claim_ids=[key])],
        )
        verify_output(output, {key: ClaimEvidence(key=key, quote=quotes[key])})
        verdict = output.sentences[0].verdict.value if output.sentences[0].verdict else "UNKNOWN"
        results.append({"id": trap["id"], "expect": trap.get("expect"), "verdict": verdict})
    return metrics.adversarial_caught(results)


def _aggregate(rows: list[dict]) -> dict[str, Any]:
    """Mean of the headline metrics across all (paper × output) rows."""
    if not rows:
        return {}
    n = len(rows)
    covs = [r["metrics"]["coverage"]["coverage"] for r in rows
            if r["metrics"]["coverage"]["coverage"] is not None]
    agg: dict[str, Any] = {}
    if covs:
        agg["key_fact_coverage"] = round(sum(covs) / len(covs), 4)
    return {
        "runs": n,
        "hallucination_rate": round(sum(r["metrics"]["hallucination_rate"] for r in rows) / n, 4),
        "faithfulness": round(sum(r["metrics"]["faithfulness"] for r in rows) / n, 4),
        "claim_precision": round(sum(r["metrics"]["claim_precision"] for r in rows) / n, 4),
        "evidence_link_validity": round(
            sum(r["metrics"]["evidence_link_validity"] for r in rows) / n, 4
        ),
        **agg,
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
    "key_fact_coverage": (">=", 0.85),  # only checked when a gold set is present
    "adversarial_caught_rate": (">=", 1.0),  # only checked when a gold set is present
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


HEADLINE_METRICS = ["hallucination_rate", "faithfulness", "claim_precision",
                    "evidence_link_validity", "quality_score"]


def _default_mlflow_uri() -> str:
    import os

    return os.environ.get("MLFLOW_TRACKING_URI") or f"file:{REPO / 'mlruns'}"


def _log_mlflow(report: dict[str, Any], uri: str, report_dir: Path) -> None:
    """Log the run to MLflow: aggregate + per-output nested runs + the report artifacts.

    Every eval run becomes a versioned, comparable experiment (docs/05 §8). Uses a
    local ``file:`` store by default so it needs no server; point MLFLOW_TRACKING_URI
    (or --mlflow-uri) at the compose ``mlflow`` service to publish to the shared UI.
    """
    import mlflow

    mlflow.set_tracking_uri(uri)
    mlflow.set_experiment("unipress-eval")
    agg = report["aggregate"]
    with mlflow.start_run(run_name=report["label"] or report["run_at"]):
        mlflow.log_params({
            "generator": report["generator"],
            "papers": ",".join(report["papers"]),
            "n_runs": agg.get("runs", 0),
        })
        for k, v in agg.items():
            if isinstance(v, (int, float)):
                mlflow.log_metric(f"agg.{k}", float(v))
        for c in report["target_checks"]:
            mlflow.log_metric(f"target_met.{c['metric']}", 1.0 if c["met"] else 0.0)
        mlflow.log_artifacts(str(report_dir), artifact_path="report")
        for row in report["rows"]:
            name = f"{row['paper']}.{row['output_type']}.{row['language']}"
            with mlflow.start_run(run_name=name, nested=True):
                mlflow.log_params({"paper": row["paper"], "output_type": row["output_type"],
                                   "language": row["language"]})
                m = row["metrics"]
                for k in HEADLINE_METRICS:
                    mlflow.log_metric(k, float(m[k]))
                mlflow.log_metric("readability.reading_ease", float(m["readability"]["reading_ease"]))
                mlflow.log_metric("readability.band_hit", 1.0 if m["readability"]["band_hit"] else 0.0)
    print(f"MLflow: logged to {uri} (experiment 'unipress-eval')")


def _push_metrics(aggregate: dict[str, Any], gateway: str) -> None:
    """Mirror the eval aggregate onto the Prometheus gauges and push to a Pushgateway."""
    import os

    from app.core.metrics import push_metrics, set_eval_metrics

    url = gateway or os.environ.get("PUSHGATEWAY_URL") or "localhost:9091"
    set_eval_metrics(aggregate)
    try:
        push_metrics(url)
        print(f"Pushed eval metrics to Pushgateway {url}")
    except Exception as exc:  # a down gateway must not fail the eval run
        print(f"! Pushgateway {url} unreachable: {exc}", file=sys.stderr)


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
                   "evidence_link_validity", "key_fact_coverage", "adversarial_caught_rate",
                   "readability_band_hit_rate", "quality_score"]:
        val = agg.get(metric)
        if val is None:  # e.g. gold-only metrics on a gold-less run
            continue
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


def _select_papers(requested: list[str] | None, synthetic: bool) -> list[dict[str, Any]]:
    if synthetic:
        return [{"id": "synthetic_fixture", "data": _synthetic_pdf(),
                 "filename": "synthetic.pdf", "language": "en"}]
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
        papers.append({"id": d["id"], "data": pdf.read_bytes(),
                       "filename": pdf.name, "language": d.get("language", "en")})
    return papers


def main() -> int:
    ap = argparse.ArgumentParser(description="UniPress DE evaluation harness")
    ap.add_argument("--papers", nargs="*", help="manifest ids (default: all research papers)")
    ap.add_argument("--outputs", nargs="*", default=DEFAULT_OUTPUTS, help="output types")
    ap.add_argument("--label", default="", help="report dir label")
    ap.add_argument("--synthetic", action="store_true",
                    help="run on an in-memory fixture paper (no external PDFs — CI eval-gate)")
    ap.add_argument("--fail-on-target-miss", action="store_true",
                    help="exit non-zero if a headline target is missed (CI eval-gate)")
    ap.add_argument("--mlflow", action="store_true", help="log the run to MLflow")
    ap.add_argument("--mlflow-uri", default=None,
                    help="MLflow tracking URI (default: $MLFLOW_TRACKING_URI or file:./mlruns)")
    ap.add_argument("--push-metrics", nargs="?", const="", default=None,
                    help="push eval gauges to a Prometheus Pushgateway "
                         "(default: $PUSHGATEWAY_URL or localhost:9091)")
    args = ap.parse_args()

    papers = _select_papers(args.papers, args.synthetic)
    if not papers:
        print("No papers to evaluate (are the sample PDFs present?)", file=sys.stderr)
        return 2

    db = _setup_infra()
    rows: list[dict[str, Any]] = []
    adversarial: dict[str, Any] = {}
    for p in papers:
        print(f"→ {p['id']} ({p['language']})")
        doc_id = _ingest(db, p["filename"], p["data"])
        gold = _load_gold(p["id"])
        for output_type in args.outputs:
            run = _generate(db, doc_id, output_type, p["language"])
            m = evaluate(run["sentences"], run["claim_keys"], output_type, p["language"], gold)
            rows.append({"paper": p["id"], "output_type": output_type,
                         "language": p["language"], "metrics": m})
            print(f"    {output_type:14s} halluc={m['hallucination_rate']:.3f} "
                  f"faith={m['faithfulness']:.3f} quality={m['quality_score']}")
        adv = run_adversarial(db, doc_id, gold)
        if adv is not None:
            adversarial[p["id"]] = adv
            print(f"    adversarial    caught={adv['caught']}/{adv['total']} "
                  f"({adv['caught_rate']:.0%})")

    agg = _aggregate(rows)
    caught = [a["caught_rate"] for a in adversarial.values() if a.get("caught_rate") is not None]
    if caught:
        agg["adversarial_caught_rate"] = round(sum(caught) / len(caught), 4)
    checks = _target_check(agg)
    report = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "generator": "deterministic-fallback",
        "papers": [p["id"] for p in papers],
        "rows": rows,
        "adversarial": adversarial,
        "aggregate": agg,
        "target_checks": checks,
    }
    out = _write_report(report, args.label)
    if args.mlflow:
        _log_mlflow(report, args.mlflow_uri or _default_mlflow_uri(), out)
    if args.push_metrics is not None:
        _push_metrics(agg, args.push_metrics)
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
