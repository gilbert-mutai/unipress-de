# `eval/` — Evaluation harness (docs/05)

Turns correctness into **reproducible, versioned numbers**. Runs the real
pipeline end-to-end in-process on the sample papers, scores each output against
the docs/05 metrics, and writes a timestamped report.

```
eval/
  run_eval.py     # the harness (committed)
  metrics.py      # pure metric functions — no app deps, unit-tested (committed)
  gold/           # <paper_id>.yaml frozen gold facts + adversarial traps (committed)
  reports/        # timestamped JSON + Markdown reports (gitignored — regenerate)
  tests/          # unit tests for metrics.py
```

## Run it

```bash
# from repo root, using the api venv (has the app package + textstat)
api/.venv/bin/python eval/run_eval.py                       # all research papers × all outputs
api/.venv/bin/python eval/run_eval.py --papers pap_smear_screening --outputs PRESS_RELEASE
api/.venv/bin/python eval/run_eval.py --label baseline      # names the report dir
api/.venv/bin/python eval/run_eval.py --fail-on-target-miss # CI eval-gate mode (non-zero on miss)
```

The default run uses the **deterministic fallback generator** and **throwaway,
service-free infra** (in-memory SQLite, hashing embedder, in-memory vector store)
— no API key, no Docker, fully reproducible. The fallback renders verified claims
verbatim, so it is grounded by construction (faithfulness ≈ 1.0, hallucination ≈ 0);
the metrics that discriminate there are **readability band-hit** (dense academic
quotes often miss the accessible-reading floor → motivates the LLM rewrite path)
and, once a gold set lands, **coverage** and **adversarial-caught**.

## Metrics (docs/05 §1, §3, §5)

| Metric | Meaning | Needs gold? |
|---|---|---|
| `hallucination_rate` | (UNSUPPORTED + CONTRADICTED) / factual sentences | no |
| `faithfulness` | mean TrustLayer confidence over factual sentences | no |
| `claim_precision` | supported factual / all factual | no |
| `evidence_link_validity` | factual sentences citing only real claim keys | no |
| `readability` | Flesch (EN) / sentence-length heuristic (HU) vs the type's floor | no |
| `coverage` | matched key gold facts / all key gold facts | **yes** |
| `adversarial_caught` | overclaim traps the TrustLayer flagged | **yes** |
| `quality_score` | trust-weighted 0–100 aggregate (§5) | partial |

Targets checked against docs/05 §6 MVP bars: hallucination ≤ 5%, faithfulness ≥ 0.90,
evidence ≥ 0.95.

## Gold set (workstream B — the ground truth)

Drop a frozen file at `eval/gold/<paper_id>.yaml` and the gold-based metrics
activate automatically. Bootstrap candidates from the extractor, then **human-verify**
(docs/05 §2.2) before committing. Schema:

```yaml
paper_id: pap_smear_screening
# Claim keys (as emitted by extraction) that MUST appear in a good output.
key_fact_claim_keys: [clm_001, clm_004, clm_012]
# Overclaim traps (docs/05 §2.3): a perturbed sentence + the verdict we expect
# the TrustLayer to return. Proves TrustLayer catches problems, not just passes text.
adversarial:
  - id: adv_001
    against_claim: clm_004        # the true claim it distorts
    perturbed: "The system achieved 98.8% accuracy across 339 smears."
    expect: CONTRADICTED          # numeric change → must be caught
```

Freezing the gold set (versioned in git, never tuned against) is what makes the
reported numbers honest — state this in the report.
