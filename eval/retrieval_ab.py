#!/usr/bin/env python3
"""Retrieval A/B — compare embedding backends on probe queries (docs/01 §1c tail, docs/05 §3).

Embeds one document's chunks with each configured backend/model, runs a small set of
labelled probe queries, and scores retrieval with hit@k + mean reciprocal rank (MRR).
Results are logged to MLflow (experiment ``unipress-retrieval-ab``) so the default
embedder choice (multilingual-e5-small vs BGE-M3, docs/07 §2.2) is a versioned, defended
number rather than an assertion. This closes the deferred P1 A/B tail.

    # runnable anywhere (no model download): the deterministic hashing baseline
    python eval/retrieval_ab.py --arms hashing

    # the real comparison (needs the models / HF cache — run on the VM)
    python eval/retrieval_ab.py --arms intfloat/multilingual-e5-small BAAI/bge-m3 --mlflow

Each ``--arms`` value is either ``hashing`` (the deterministic stub) or a
SentenceTransformer model id used with the real backend.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(REPO / "api"))

# The fixture paper + its probe queries. Each probe names a substring that a
# relevant chunk must contain — the ground-truth relevance label.
from run_eval import _setup_infra, _ingest, _synthetic_pdf  # noqa: E402

PROBES: list[dict[str, str]] = [
    {"query": "How accurate is the screening system?", "expect": "88.8% accuracy"},
    {"query": "How many clinical samples were used?", "expect": "339 clinical samples"},
    {"query": "What are the limitations of the approach?", "expect": "born-digital images"},
    {"query": "How much did false negatives drop?", "expect": "false negatives by 42%"},
    {"query": "How many cell predictions were made?", "expect": "12 million"},
]


def _configure_arm(arm: str) -> dict[str, str]:
    """Point the embedder at one arm (hashing stub or a real SentenceTransformer model)."""
    from app.core.settings import get_settings
    from app.retrieval import embedder as _emb
    from app.retrieval import service as _rsvc

    settings = get_settings()
    if arm == "hashing":
        settings.embed_backend = "hashing"
    else:
        settings.embed_backend = "sentence-transformers"
        settings.embed_model = arm
    settings.vector_backend = "memory"
    _emb.reset_embedder()
    _rsvc.reset_vector_store()
    return {"backend": settings.embed_backend, "model": getattr(settings, "embed_model", "")}


def _score_arm(db: Any, doc_id: str, k: int) -> dict[str, float]:
    from app.retrieval.service import search

    hits_at_k, reciprocal_ranks = 0, []
    for probe in PROBES:
        hits = search(doc_id, probe["query"], k=k)
        rank = next(
            (i + 1 for i, h in enumerate(hits) if probe["expect"].lower() in h.text.lower()),
            None,
        )
        if rank is not None:
            hits_at_k += 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)
    n = len(PROBES)
    return {
        "hit_at_k": hits_at_k / n,
        "mrr": sum(reciprocal_ranks) / n,
        "probes": float(n),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Retrieval A/B over embedding backends")
    ap.add_argument("--arms", nargs="+", default=["hashing"],
                    help="'hashing' or SentenceTransformer model ids")
    ap.add_argument("--k", type=int, default=5, help="top-k for hit@k / MRR")
    ap.add_argument("--mlflow", action="store_true", help="log arms to MLflow")
    ap.add_argument("--mlflow-uri", default=None)
    args = ap.parse_args()

    db = _setup_infra()
    pdf = _synthetic_pdf()

    results = []
    for arm in args.arms:
        cfg = _configure_arm(arm)
        doc_id = _ingest(db, f"{arm}.pdf", pdf)  # re-embed the corpus under this arm
        score = _score_arm(db, doc_id, args.k)
        results.append({"arm": arm, **cfg, **score})
        print(f"{arm:36s} hit@{args.k}={score['hit_at_k']:.2f} mrr={score['mrr']:.3f}")

    if args.mlflow:
        import mlflow

        from run_eval import _default_mlflow_uri

        mlflow.set_tracking_uri(args.mlflow_uri or _default_mlflow_uri())
        mlflow.set_experiment("unipress-retrieval-ab")
        for r in results:
            with mlflow.start_run(run_name=r["arm"]):
                mlflow.log_params({"backend": r["backend"], "model": r["model"], "k": args.k})
                mlflow.log_metric("hit_at_k", r["hit_at_k"])
                mlflow.log_metric("mrr", r["mrr"])
        print("MLflow: logged retrieval A/B (experiment 'unipress-retrieval-ab')")

    winner = max(results, key=lambda r: (r["mrr"], r["hit_at_k"]))
    print(f"\nBest MRR: {winner['arm']} ({winner['mrr']:.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
