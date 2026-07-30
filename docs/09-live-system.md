# 09 — The Live System

> **This is the as-built guide.** Docs [`01`](01-project-definition.md)–[`08`](08-dev-plan.md) are the design record — what was decided before code, and why. This document describes what is actually deployed and running, and how to use and operate it. Where the two disagree, this one is right.

**Live:** <https://unipress.gilbertmutai.com> · Last verified 30 Jul 2026.

---

## 1. What it does

UniPress DE turns a research paper (PDF) into publication-ready communication material — press release, public article, social post, executive summary and a 60-second video script — in **Hungarian and English**, where every factual sentence is traceable to a verbatim quote in the source and independently checked before a human sees it.

The difference from a general-purpose AI tool is that provenance is structural, not promised. The paper is first decomposed into **quote-anchored claims**; generation is *bound* to those claims and must cite them; each generated sentence is then verified against the exact quote it cites. A sentence that cites nothing, or overstates what its quote supports, is flagged or blocked — automatically, before review.

## 2. Try it in three minutes

| Step | Where |
|---|---|
| 1. Open the app | <https://unipress.gilbertmutai.com> |
| 2. Pick an output type + language, press **Generate** | Step 2 on the page |
| 3. Read the evidence trail — per-sentence verdict, confidence, cited quote | Step 3, "Review the evidence" |
| 4. Click a sentence to see its quote **highlighted in the original PDF** | Evidence panel |
| 5. Export the bilingual PDF/HTML with attribution | Export button |
| 6. Watch the live ops + eval metrics | <https://unipress.gilbertmutai.com/grafana/d/unipress-overview> |
| 7. Read the API | <https://unipress.gilbertmutai.com/api/docs> |

A paper is already ingested, so generation is immediate. Uploading your own PDF works too (≤30 MB); ingestion takes a couple of minutes and its progress is shown.

**What to look for.** The interesting output is not the fluent prose — any model does that. It is the sentence the system *refuses to stand behind*. On the demo paper the generator wrote that LightGBM stood out "due to its robust architecture and sophisticated computational techniques"; the TrustLayer flagged it, because the paper reports performance metrics and says nothing about architecture. That flag is the product.

## 3. How it works

The pipeline and the reasoning behind each stage are in the [README](../README.md#how-it-works), with a diagram. In brief:

```
parse → chunk → extract claims (quote-verified) → embed
                              ↓
          claim-bound generation → TrustLayer → human review → export
```

Two design points worth restating, because they are what a technical reviewer will ask about:

- **The quote guardrail is load-bearing.** A candidate claim is discarded unless its quote is found verbatim in the parsed source. Every claim in the store is therefore *already proven* to exist in the paper, before generation runs. That is what makes source-highlighting possible.
- **Generation is claim-bound, not retrieval-augmented.** Classic RAG fetches top-k chunks and lets the model write over them, which leaves nothing structurally tying an output sentence to a source span. The vector store here serves search and evidence lookup; generation reads the claim store and cites claim IDs.

### The trust checks, in order

Per factual sentence, with the premise being only the quotes of the claims *that sentence cites*:

1. **Numeric check** — a number the quote doesn't corroborate is a hard fail (`CONTRADICTED`). Locale-aware: Hungarian decimal commas and spelled-out source numbers are handled, and digits inside identifiers are not mistaken for quantities.
2. **Tier-1 entailment** — mDeBERTa XNLI (`MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`), local, no API cost, multilingual.
3. **Tier-2 judge** — `gpt-4o-mini`, run when entailment is below 0.85 or the sentence contains numbers. Returns a supported-fraction and a written rationale.
4. **Confidence** — `0.4·entail + 0.4·judge + 0.2·quote_overlap`, minus a numeric penalty. `≥0.70` → SUPPORTED, `≥0.45` → INTERPRETATION, below → UNSUPPORTED.

Tier-1 and Tier-2 belong together: mDeBERTa is strict about a sentence adding specifics its quote doesn't state, so with the judge disabled a whole output can read UNSUPPORTED. Measured on one output: 9/9 unsupported with NLI alone, 2/12 with the judge on.

## 4. Using the API

Everything is under `/api` (nginx strips the prefix). Interactive docs at [`/api/docs`](https://unipress.gilbertmutai.com/api/docs).

| Endpoint | Purpose |
|---|---|
| `POST /api/documents` | Upload a PDF (≤30 MB). Creates the document + job, enqueues ingestion |
| `GET /api/documents/{id}` | Ingestion status and progress |
| `GET /api/documents/{id}/claims` | The claim store — quotes, spans, claim types |
| `GET /api/documents/{id}/chunks` | Parsed chunks (inspection) |
| `POST /api/documents/{id}/search` | Semantic search over the embedded chunks — the retrieval step |
| `POST /api/documents/{id}/outputs` | Generate one output (`output_type`, `language`, `refresh`) |
| `GET /api/documents/{id}/outputs` | List a document's outputs |
| `GET /api/documents/outputs/{output_id}` | An output with per-sentence verdicts, confidence, rationales |
| `GET /api/documents/outputs/{output_id}/render?format=html\|pdf` | Publishable render with evidence trail + attribution |
| `GET /api/documents/{id}/pages/{n}.png?bbox=x0,y0,x1,y1` | Source page as PNG with the cited span highlighted |
| `GET /api/jobs/{job_id}` | Poll any job (ingestion or generation) |
| `GET /api/health` · `GET /api/ready` | Liveness · readiness (503 when the database is unreachable) |

`output_type` is one of `PRESS_RELEASE`, `ARTICLE`, `SOCIAL`, `EXEC_SUMMARY`, `VIDEO_SCRIPT`; `language` is `en` or `hu`.

A full run, start to finish:

```bash
API=https://unipress.gilbertmutai.com/api

# 1. upload, then poll until status is "done"
DOC=$(curl -sS -X POST "$API/documents" -F file=@paper.pdf | jq -r .id)
curl -sS "$API/documents/$DOC" | jq '{status, progress}'

# 2. generate (returns a job; result is the output id)
JOB=$(curl -sS -X POST "$API/documents/$DOC/outputs" \
        -H 'content-type: application/json' \
        -d '{"output_type":"PRESS_RELEASE","language":"hu"}' | jq -r .id)
OUT=$(curl -sS "$API/jobs/$JOB" | jq -r .result)

# 3. read the evidence trail
curl -sS "$API/documents/outputs/$OUT" \
  | jq '.sentences[] | {text, role, verdict, confidence, claim_ids, rationale}'

# 4. render it
curl -sS "$API/documents/outputs/$OUT/render?format=html" -o output.html
```

**Repeat requests are free and instant.** A request for a (document, type, language) that already has an output returns it as an already-complete job with `stage: "cached"` — no model call, typically well under a second. Pass `"refresh": true` to force a fresh generation. This is deliberate: it removes live rate-limit and latency risk from a demo, and the durable outputs table is the cache rather than a second copy that could disagree with it.

## 5. What runs where

Single public origin behind nginx; **only ports 22, 80 and 443 are reachable** from outside. Everything else talks over the Docker network.

| Path | Serves |
|---|---|
| `/` | Next.js frontend |
| `/api/*` | FastAPI (prefix stripped; `root_path=/api` so Swagger resolves its own schema) |
| `/grafana/*` | Grafana, anonymous access downgraded to **Viewer** — read-only in public |

Internal only: PostgreSQL, Redis, Chroma, the Celery worker (+ its `:9100` metrics), Flower, Prometheus, Pushgateway, Tempo, MLflow, the OTel collector.

Services are grouped by compose **profile** — `core`, `observability`, `ml`, `local-llm`. Nothing starts without a profile selected, which is a common trap: a bare `docker compose build` reports "No services to build".

## 6. Configuration that matters

The LLM path is **doubly gated** — a key *and* the matching flag — so nothing spends by accident. With flags off, the system runs a deterministic fallback and costs nothing, which is what CI and local development use.

| Variable | Production | Notes |
|---|---|---|
| `OPENAI_API_KEY` | set | Must be passed into the containers, not merely present in `.env` |
| `LLM_GENERATION` | `true` | `gpt-4o` writes the outputs |
| `LLM_JUDGE` | `true` | `gpt-4o-mini` Tier-2 judge |
| `NLI_BACKEND` | `nli` | mDeBERTa; downloads ~1 GB into the hf-cache volume on first use |
| `LLM_EXTRACTION` | `false` | See limitations — deliberately off |
| `ROOT_PATH` | `/api` | Set only in the production overlay |

**Changing `.env` has no effect until the containers are recreated** (`docker compose up -d --force-recreate api worker`). A rotated key was silently ignored for minutes because of this.

## 7. Operating it

```bash
cd /opt/unipress-de                                   # on the VM

DOMAIN=unipress.gilbertmutai.com ops/deploy.sh        # pull → build → migrate → up → verify
ops/deploy.sh --no-build                              # restart only (env/compose change)
ops/deploy.sh --force-rebuild                         # when a cached layer is stale

ops/backup.sh                                         # also runs nightly by cron
ops/restore.sh --list                                 # what snapshots exist
ops/restore.sh --latest --rehearse                    # verify a snapshot, zero downtime
ops/restore.sh --latest                               # actual recovery (destructive, prompts)

ops/pregenerate.sh <document_id>                      # warm all 5 types × 2 languages
ops/nginx/test-routing.sh                             # assert the proxy contract
```

Two things `deploy.sh` does that are easy to get wrong by hand: it runs `alembic upgrade head` **explicitly** (compose is otherwise satisfied by an unchanged `migrate` image's previous exit, silently skipping a new migration), and it **reloads nginx** after `up -d` (recreated containers get new IPs; nginx resolves upstreams at config load, so without a reload every `/api/*` request 502s). The nginx config also re-resolves per request, which covers a container that restarts on its own.

Backups are the nightly `pg_dump` plus Chroma, uploaded-PDF and MLflow volume snapshots in `/opt/unipress-backups`, pruned after 7 days. `--rehearse` is the one to run regularly: it proves the snapshot restores without stopping anything.

## 8. What is measured

- **Grafana** ([`/grafana/d/unipress-overview`](https://unipress.gilbertmutai.com/grafana/d/unipress-overview)) — 16 panels: per-stage latency and throughput, Celery queue depth, LLM token rate and cost, API p95, plus **live eval metrics** as first-class series.
- **Prometheus** scrapes api, worker and a **Pushgateway** that carries batch eval metrics — that is how `hallucination_rate`, `faithfulness` and `coverage` reach the public dashboard. Not exposed publicly; Grafana is the read view.
- **Eval harness** — `python eval/run_eval.py` runs the real pipeline in-process against the gold + adversarial sets and writes a timestamped JSON + Markdown report; `--mlflow` versions every run; `--fail-on-target-miss` is the CI gate.

Current honest numbers on the demo paper: **adversarial traps caught 5/5**, zero `CONTRADICTED` across all ten warm outputs, English confidence 0.58–0.89, Hungarian 0.38–0.62, `key_fact_coverage` **0.20 — below target** (see limitations). Generation costs about **$0.017 per output**.

## 9. Known limitations

Stated plainly, because a reviewer will find them anyway:

- **`key_fact_coverage` misses its target (0.20).** The heuristic extractor ranks claims by its own importance score, so the six human-curated must-not-miss facts are not all selected. This is the gap the LLM extraction path is meant to close.
- **`LLM_EXTRACTION` is off deliberately.** Claim keys are positional (`clm_001`, `clm_002`, …), so re-extraction renumbers them — which would silently invalidate the frozen gold set's `key_fact_claim_keys` *and* the adversarial traps' `against_claim` references, including the canonical 88.8 → 98.8 trap. Enabling it is a post-demo change paired with a deliberate gold re-freeze.
- **Hungarian confidence trails English** (0.38–0.62 vs 0.58–0.89, with more UNSUPPORTED). Structural: `quote_overlap` is 0.2 of the confidence blend, and a Hungarian sentence against an English quote has near-zero lexical overlap, so Hungarian forfeits that term. Candidate fix: redistribute that weight when output and source languages differ. Entailment itself is unaffected — cross-lingual NLI scores a Hungarian paraphrase of an English quote at 0.998.
- **SSH hardening is not applied.** Root login with password authentication is still enabled on the VM. `ops/harden.sh` closes it (ufw + key-only sshd) but needs a keyed non-root user created first, or it removes the only way in.
- **MLflow has no public URL.** The versioned eval report exists but isn't linkable for a reviewer; it ships no authentication of its own, so exposing it needs basic-auth at nginx.
- **Only one paper is ingested in production.** Three further gold candidates remain unverified locally.
- **Video rendering (TTS + assembly) is out of scope** — the video output is a timed scene table, per the scope ladder in [`08` §10](08-dev-plan.md).

## 10. Running it yourself

```bash
git clone git@github.com:gilbert-mutai/unipress-de.git && cd unipress-de
cp .env.example .env              # works with no API key — deterministic fallback
docker compose --profile core up
# add --profile observability for Prometheus/Grafana/Tempo, --profile ml for MLflow
```

Local URLs, and the tests:

| URL | Service |
|---|---|
| <http://localhost:3000> | Frontend |
| <http://localhost:8000/docs> | API + Swagger |
| <http://localhost:3001> | Grafana (`admin` / `$GRAFANA_ADMIN_PASSWORD`) |
| <http://localhost:9090> · <http://localhost:3200> · <http://localhost:5000> · <http://localhost:5555> | Prometheus · Tempo · MLflow · Flower |

```bash
cd api && pytest -q                  # api suite, no services needed
pytest ../eval -q                    # metric unit tests
python ../eval/run_eval.py --help    # the eval harness
```

No key, no Docker registry access and no GPU are required for the test suites: they use an in-memory SQLite database, a hashing embedder and an in-memory vector store.
