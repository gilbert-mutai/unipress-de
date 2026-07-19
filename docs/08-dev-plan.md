# UniPress DE — MVP Development Plan

> **DEIK.AI Challenge 2026 · Category 2.C** · Companion to [`07-tech-stack.md`](07-tech-stack.md)
> The build sequenced as milestones against the **25 September 2026** demo deadline, on the production skeleton from `07`.
> Anchor date: 19 July 2026 · ~10 working weeks · Solo build · Possible AI Sprint Final: 9–10 October 2026.

---

## 0. How this plan is built

This is not a wishlist of features — it is a **critical path** to a demoable, trustworthy system, sequenced so that risk is retired early and the trust core is proven before polish begins.

Three engineering principles shape the sequence:

- **Walking skeleton first.** Week 1 delivers `docker compose up` bringing the *whole* system online with one hard-coded claim flowing API → worker → DB → UI. Every service, the CI pipeline, and one trace exist before any feature does. Integration risk is paid down on day one, not discovered in September.
- **Thin vertical slice, then deepen.** One real sample paper is pushed end-to-end (parse → claim → generate → verify → render) as early as possible; each stage is then deepened in place. We are never in a state where "nothing works yet" — the demo exists from Phase 2 and improves weekly.
- **Eval front-loaded.** The gold + adversarial sets (per [`06`](06-dataset-strategy.md)) are authored *alongside* the extractor, so the moment generation works there is already a scoreboard. Evaluation is a build-time instrument, not an afterthought.

Effort is stated in **focused engineering-days** (a solo builder's realistic ~5-day week with buffer). The plan reserves the final week for freeze, rehearsal, and contingency.

---

## 1. Timeline at a glance

| # | Phase | Weeks | Dates (2026) | Focus | Cumulative days |
|---|---|---|---|---|---|
| **P0** ✅ | Foundation & walking skeleton | W1 | Jul 20 – Jul 26 | Compose up, CI, ports, one round-trip | 5 |
| **P1** 🚧 | Ingestion, claim store & retrieval | W2–W3 | Jul 27 – Aug 9 | PDF → verified claims → RAG · *1a ingestion done* | 15 |
| **P2** | Generation + TrustLayer (**trust core**) | W4–W5 | Aug 10 – Aug 23 | Claim-bound gen, NLI + judge + scoring | 25 |
| **P3** | Outputs & bilingual rendering | W6 | Aug 24 – Aug 30 | 5 output types × HU/EN, evidence trail | 30 |
| **P4** | Review dashboard (**the product**) | W7–W8 | Aug 31 – Sep 13 | Upload → review-with-highlights → export | 40 |
| **P5** | Evaluation, MLflow & observability | W8–W9 | Sep 7 – Sep 20 | Harness, eval-gate, Grafana board | 47 |
| **P6** | Deploy, harden & demo | W9–W10 | Sep 14 – Sep 25 | Angani VM, TLS, rehearse, **freeze** | 52 |

> P5 overlaps P4 by design — the gold set and metrics accrue while the frontend is built. **Feature freeze: Mon 22 Sep**; Tue 23 – Fri 25 is rehearsal + contingency buffer.

```mermaid
gantt
    dateFormat  YYYY-MM-DD
    axisFormat  %b %d
    title UniPress DE — MVP build (Jul 20 → Sep 25, 2026)

    section Foundation
    P0 Skeleton + CI            :p0, 2026-07-20, 7d

    section Trust pipeline
    P1 Ingest + claims + RAG    :p1, after p0, 14d
    P2 Generation + TrustLayer  :p2, after p1, 14d

    section Product
    P3 Outputs + bilingual      :p3, after p2, 7d
    P4 Review dashboard         :p4, after p3, 14d

    section Prove + ship
    P5 Eval + observability     :p5, 2026-09-07, 14d
    P6 Deploy + harden          :p6, 2026-09-14, 9d
    Freeze + rehearsal          :milestone, freeze, 2026-09-22, 0d
    Demo deadline               :milestone, dl, 2026-09-25, 0d
```

---

## 2. Phase 0 — Foundation & walking skeleton

**Weeks:** W1 (Jul 20–26) · **Effort:** ~5 days · **Depends on:** nothing (start immediately)

**Objective.** Stand up the entire production skeleton from [`07` §5](07-tech-stack.md) so that `docker compose up` brings every core service healthy and a single hard-coded claim round-trips API → Celery worker → Postgres → Next.js — with CI green and one distributed trace visible. This retires integration risk before any feature is written.

**Deliverables**
- Repo layout per `07` §5 (`api/`, `worker/`, `frontend/`, `ops/`, `data/`, `eval/`).
- `docker-compose.yml` with **profiles** (`core | observability | ml | local-llm`) + `override` for dev; `.env.example`.
- `pydantic-settings` config; Postgres 16 + **Alembic** initial migration; Redis; **Celery** app + **Flower**.
- Empty **ports** (`VectorStore`, `LLMGateway`, `Storage`, `TaskDispatch`) with in-memory/stub adapters.
- FastAPI `/health` + `/ready`; a demo Celery task chain; Next.js shell that reads task state.
- **CI** (GitHub Actions): ruff → mypy → pytest against ephemeral services; **pre-commit** installed.
- OTel + Prometheus instrumentation wired on api + worker (observability profile).

**Definition of Done**
- `docker compose --profile core up` → all services healthy; `--profile observability` adds OTel/Prom/Tempo/Grafana.
- A submitted job flows through Celery and its result is readable via the API and shown in the UI shell.
- CI is green on `main`; one end-to-end trace (api → worker) is visible in Tempo.

**Risks:** dependency/version friction (torch CPU wheel, WeasyPrint system libs) → pin versions, bake into images early. Docker resource pressure on the dev machine → use profiles to run lean locally.

**Status — ✅ delivered (19 Jul 2026).** Repo scaffolded (`api/`, `worker/`, `frontend/`, `ops/`); Compose profiles (`core | observability | ml | local-llm`) validate; api+worker share one image (ML split deferred, see `worker/README.md`); Alembic `0001_initial` creates the `jobs` table; the four ports ship with stub adapters; `/health` + `/ready` live; the demo Celery chain (`ingest → parse → embed → verify → finalize`) runs. **Verified live:** `docker compose --profile core up` healthy, a job round-trips API → Celery → Postgres to `done`, worker logs each stage as structured JSON. Backend CI-clean (ruff, mypy, 6 pytest); frontend type-checks + builds. **Deferred to a follow-up within P1:** confirming the api→worker trace lands in Tempo (instrumentation is wired), and the dev-convenience code bind-mount/hot-reload.

---

## 3. Phase 1 — Ingestion, claim store & retrieval

**Weeks:** W2–W3 (Jul 27 – Aug 9) · **Effort:** ~10 days · **Depends on:** P0

**Objective.** Turn a real sample PDF into a **queryable, span-linked claim store** with working retrieval — the factual substrate everything downstream is constrained to. Per [`03` §2–4](03-ai-pipeline.md).

**Deliverables**
- **Parsing** (PyMuPDF): text + page/section/**bounding-box** spans; Docling for complex tables/layouts; image-only-page detection → warn (no OCR, per `03`).
- **Chunking** with structure + positional metadata preserved for UI highlight.
- **Claim extraction** → `Claim` records (doc `03` contract) each with `source_span` (page/section/verbatim quote) and a **quote-verification** step that rejects any claim whose quote is not found in the source text.
- **Embeddings** (BGE-M3, local in worker) → **Chroma** via the `VectorStore` port; **bge-reranker-v2-m3** rerank.
- Celery **chain**: `ingest → parse → chunk → extract → embed`, with per-stage retries + idempotency keys.
- **Eval (front-loaded):** author gold facts + adversarial perturbations for **2 papers (1 EN + 1 HU)** alongside the extractor ([`06` §7](06-dataset-strategy.md)).

**Definition of Done**
- The 4 sample research papers + 1 HU curriculum parse cleanly (HU accents + multi-column confirmed).
- A chosen sample paper yields a claim store where **every claim's quote is verifiably present** in the source.
- Retrieval returns relevant chunks for probe queries in **both HU and EN**; retrieval A/B (BGE-M3 vs `text-embedding-3-large`) logged to MLflow to confirm the default.

**Risks:** multi-column / table extraction quality on the papers → GROBID is the pre-scoped fallback (`07` §2.1), introduced only against a measured need. HU tokenization/accents → verified explicitly on the curriculum in DoD.

**Status — 🚧 in progress. Sub-phases 1a (ingestion) + 1b (claim extraction) ✅ delivered (19 Jul 2026).**
- **1a — Built:** PyMuPDF parser (text + bbox blocks, image-only detection → warning); structure-aware chunker (page-bounded chunks, best-effort section detection, exact `SourceSpan` provenance); `Document`/`Chunk` tables + Alembic `0002`; `Storage` port wired for uploads (shared api/worker volume); `POST /documents` + `GET /documents/{id}` + `/chunks`; Celery chain `parse → chunk → finalize`. **Verified:** all 6 sample PDFs parse cleanly (page counts match manifest; HU accents preserved; **0 chunk-provenance failures**); end-to-end EN 10p/94 chunks, HU 9p/19 chunks.
- **1b — Built:** the **quote-verification guardrail** (docs/03 §2.3 — exact + whitespace-flexible span location; rejects any quote not literally in source); deterministic **heuristic extractor** (sentence split, cue-based typing into QUANTITATIVE/FINDING/METHOD/LIMITATION, numeric flag, importance ranking, dedup) as the no-key default; **LiteLLM `LLMGateway`** adapter + schema-constrained **LLM extractor** behind the same guardrail, **opt-in** via `llm_extraction` flag + key (default off, so zero spend by default); `Claim` table + Alembic `0003`; `extract` Celery stage (`parse → chunk → extract → finalize`); `GET /documents/{id}/claims`. **Verified:** 0 claim-provenance failures on all 4 papers; end-to-end pap-smear paper → **76 claims** with correct types + spans (e.g. QUANTITATIVE "over 12 million individual cell predictions", p1). 20 pytest, ruff + mypy clean.
- **Known gap:** heuristic extractor yields 0 claims on the HU curricula (English cues, low claim density) — the LLM path or HU cues address this later; curricula drive programme-promotion outputs, not claim-dense press releases.
- **1c — Built:** the retrieval layer (RAG "R"). `Embedder` port with a **SentenceTransformer** backend (**default `multilingual-e5-small`**, HU+EN; **BGE-M3 swappable via `EMBED_MODEL`** on the VM) + a deterministic **hashing** stub for tests; **`VectorStore` port redesigned** (`add`/`query`/`delete` with embeddings + metadata) with **`ChromaVectorStore`** (HTTP/persistent) and `InMemoryVectorStore`; `embed` Celery stage (`parse → chunk → extract → embed → finalize`); **`POST /documents/{id}/search`** (embed query → Chroma similarity → span-linked hits); Chroma service + HF-cache volume in compose. **Verified:** hashing+in-memory tests green; real semantic retrieval with e5-small on sample papers (HU + EN queries return relevant chunks — see below).
  - **Deviation (recorded):** runtime embed default is `multilingual-e5-small`, not doc `07`'s BGE-M3 — chosen for a fast, light dev/demo loop; BGE-M3 remains the documented VM default and is a one-line `EMBED_MODEL` swap. The **worker-image split** (`worker/`) is likewise **deferred** — with a light model the shared api/worker image is fine; the split lands when BGE-M3/GPU move onto the VM.
- **Remaining in P1:** `bge-reranker-v2-m3` rerank (optional, deferred — flag-gated), and the front-loaded **gold + adversarial eval set** (1 EN + 1 HU) + retrieval **A/B → MLflow** (moves toward Phase 5's harness). After that, Phase 1 is complete → Phase 2 (Generation + TrustLayer).

---

## 4. Phase 2 — Generation + TrustLayer (the trust core)

**Weeks:** W4–W5 (Aug 10–23) · **Effort:** ~10 days · **Depends on:** P1

**Objective.** Prove the differentiator: **claim-bound generation** whose every sentence is classified, grounded, and confidence-scored — with unsupported and numerically-wrong claims blocked. This is the single most important phase; it is scheduled at the midpoint so it has slack on both sides.

**Deliverables**
- **Claim-bound generator** via **LiteLLM** gateway (OpenAI GPT-4o/4.1 default), citation-aware, structured output, per-stage routing + centralized retry/timeout/cost (`tenacity`).
- **TrustLayer T1** — DeBERTa-v3 MNLI (EN) / mDeBERTa-v3-XNLI (HU) entailment gate; contradiction/entail cutoffs per [`07` §2.3](07-tech-stack.md).
- **TrustLayer T2** — LLM judge on `gpt-4o-mini` for sentences that pass T1 but need support-fraction adjudication.
- **Confidence score** per [`03` §5.4](03-ai-pipeline.md): weighted blend (NLI entailment + judge supported-fraction + numeric/entity overlap) with a **hard numeric-mismatch penalty**; sentence typing (fact / interpretation / framing / unsupported); export threshold as typed config.

**Definition of Done**
- A sample paper produces a **press release** where each sentence carries a type, a grounding link, and a score.
- An **unsupported claim is blocked or flagged**; a numeric perturbation from the adversarial set (e.g. `88.8% → 98.8%`) triggers the numeric penalty and is caught.
- Thresholds/weights tuned against the frozen gold set; the tuning run is versioned in MLflow.

**Risks:** local ML memory footprint (BGE-M3 + DeBERTa + reranker ≈ 5–6 GB) → models loaded **once in the worker** per `07` §7; validate the memory budget on the target VM spec early. Judge cost/latency → T1 gates most sentences off the paid judge; Redis memoization on repeated claims.

---

## 5. Phase 3 — Outputs & bilingual rendering

**Weeks:** W6 (Aug 24–30) · **Effort:** ~5 days · **Depends on:** P2

**Objective.** Fan out the one verified claim store into all five audience-adapted artifacts, in **Hungarian and English**, each carrying its evidence trail and source attribution. Per [`04`](04-content-outputs.md).

**Deliverables**
- Five `OutputSpec`s: **press release · lay article · social posts · executive summary · 60-second video script** (script = structured JSON scenes → readable table; TTS/assembly stays a stretch module).
- **Bilingual** HU/EN generation — audience-adapted rewriting, not literal translation — with per-language TrustLayer verification.
- **Rendering:** Jinja2 templates → WeasyPrint PDF/HTML; golden-file tests on output structure.
- **Attribution footer** (title, authors, DOI, license) on every output, sourced from [`data/manifest.yaml`](../data/manifest.yaml).

**Definition of Done**
- All five outputs render in both languages for a sample paper, each with an inline evidence trail and correct attribution.
- Rendering is deterministic and covered by golden-file tests; HU output verified end-to-end on a HU-native source.

**Risks:** HU generation quality vs. EN → per-language verification catches drift; the HU curriculum is the native test bed. Output sprawl → all five are the *same* `OutputSpec` abstraction over one claim store; deferred formats (newsletter/FAQ/slides) stay out (`04` §deferred).

---

## 6. Phase 4 — Review dashboard (the product)

**Weeks:** W7–W8 (Aug 31 – Sep 13) · **Effort:** ~10 days · **Depends on:** P3

**Objective.** Build the evidence-review UX — *the product and the demo*. A comms officer uploads a paper, watches it process, and reviews output with each claim highlighted against its source quote side-by-side, then accepts/edits/flags and exports.

**Deliverables**
- **Upload** flow → enqueue → **progress tracking** (poll/SSE) against Celery state.
- **Evidence-review view:** generated sentence ↔ source-span highlight (using P1 bounding boxes), sentence-type badges + confidence, blocked/flagged claims surfaced.
- **Accept / edit / flag** per element; **export** to bilingual PDF.
- Single-origin routing (frontend + `/api`), React Query data layer, Zod-validated contracts.

**Definition of Done**
- Full browser journey works end-to-end: **upload → progress → review-with-highlights → accept/edit → export bilingual PDF** — the exact 90-second live-demo path from [`01` §pitch](01-project-definition.md).
- Flagged/blocked claims and confidence scores are legible to a non-technical reviewer.

**Risks:** frontend is the largest single chunk of UI work for a backend-leaning solo builder → keep it purposeful (review UX only, no auth/settings sprawl — auth is a production graduation, `02` §8); reuse the highlight primitive across all output types.

---

## 7. Phase 5 — Evaluation, MLflow & observability

**Weeks:** W8–W9 (Sep 7–20, overlapping P4) · **Effort:** ~7 days · **Depends on:** P1 gold set; P2 trust core

**Objective.** Turn correctness and operability into **visible, versioned, live** signals — the jury-facing proof that the system works and is production-operated. Per [`05`](05-evaluation.md) + [`07` §2.8–2.9](07-tech-stack.md).

**Deliverables**
- `eval/run_eval.py` harness: **RAGAS** (faithfulness) + custom hallucination/coverage/numeric-accuracy metrics + **textstat** readability, over the gold + adversarial sets.
- **MLflow** tracking of every eval run (params, metrics, model/threshold versions, artifacts) → reproducible, comparable numbers.
- **CI eval-gate:** the harness runs on a small fixed set in GitHub Actions; the build **fails if hallucination rate regresses** past threshold (`07` §8).
- **Grafana** board: per-stage latency, LLM token cost, cache-hit, queue depth, and **live eval metrics** (hallucination rate, faithfulness, coverage) as first-class series — a headline demo visual.

**Definition of Done**
- One command produces a versioned MLflow eval report meeting the `05` §metrics MVP targets.
- CI eval-gate demonstrably fails on an injected regression.
- Grafana shows live ops + eval metrics with the full stack running.

**Risks:** eval targets not met by MVP → the harness *is* the tuning loop (threshold/weight tuning from P2 continues here); scope the gold set to the sample corpus first, external papers optional (`06` §7).

---

## 8. Phase 6 — Deploy, harden & demo

**Weeks:** W9–W10 (Sep 14–25) · **Effort:** ~8 days · **Depends on:** P4 (product), P5 (proof)

**Objective.** Ship the fully-hosted system to a public HTTPS URL judges can try, harden it, and rehearse the pitch. Per [`07` §9](07-tech-stack.md).

**Deliverables**
- **Angani VM** (Ubuntu 24.04, 8 vCPU / 16 GB) provisioned; Docker + Compose; profiled production topology.
- **Nginx + Certbot** TLS on `unipress.gilbertmutai.com`; API under `/api` (single origin); DNS A-record; port 80 for ACME only.
- **Ops:** named volumes, firewall (80/443 + restricted SSH), `.env` secrets, nightly `pg_dump` + Chroma/MLflow snapshots, scripted redeploy (`git pull` + `compose up -d --build` + `alembic upgrade head`).
- **Demo safety:** pre-generated demo outputs + Redis caching to remove live rate-limit/latency risk; a rehearsed 3-minute + 90-second demo path.

**Definition of Done**
- Public HTTPS URL live and reachable; a paper runs end-to-end on the server.
- Backups verified (restore tested once); Grafana board reachable behind auth.
- **Feature freeze Mon 22 Sep**; demo rehearsed twice; Tue 23 – Fri 25 held as contingency buffer.

**Risks:** deployment-day surprises → deploy the skeleton to the VM early (a smoke deploy in P0/P1 slack), so P6 is a redeploy, not a first deploy. Live-demo fragility → pre-generated outputs + cache are the safety net; the public URL de-risks "works on my laptop."

---

## 9. Dependency graph

```mermaid
flowchart LR
    P0[P0 · Skeleton + CI] --> P1[P1 · Ingest + claims + RAG]
    P1 --> P2[P2 · Generation + TrustLayer]
    P2 --> P3[P3 · Outputs + bilingual]
    P3 --> P4[P4 · Review dashboard]
    P1 -. gold set .-> P5[P5 · Eval + observability]
    P2 -. trust core .-> P5
    P4 --> P6[P6 · Deploy + harden + demo]
    P5 --> P6
    P0 -. smoke deploy .-> P6
```

The **critical path is P0 → P1 → P2 → P3 → P4 → P6**. P5 runs parallel to P4 (it consumes P1's gold set and P2's trust core, not P3/P4). A smoke deploy to the VM during early slack makes P6 a redeploy.

---

## 10. Scope-control ladder (what gets cut, in order)

If the build falls behind, features are dropped **from the bottom up** — the trust core and the review UX are never sacrificed, because they *are* the differentiator and the demo.

| Cut order | Item | Fallback if cut | Already scoped as |
|---|---|---|---|
| 1 (first to go) | Video **rendering** (TTS + assembly) | Ship the polished script table | Stretch module (`02` §7) |
| 2 | External gold papers beyond the sample set | Evaluate on the 6 provided docs only | Optional (`06` §7) |
| 3 | GROBID structured parsing | PyMuPDF + Docling only | Conditional (`07` §2.1) |
| 4 | Loki log shipping | structlog JSON to stdout | Optional (`07` §2.8) |
| 5 | Local Ollama privacy-demo path | OpenAI-only for the demo | Optional (`07` §2.4) |
| 6 | Social + exec-summary output types | Ship press release + lay article + script | 3 of 5 outputs still a strong demo |
| **Never cut** | Claim store + TrustLayer + evidence-review UI + bilingual + eval | — | The core value proposition (`01`) |

---

## 11. Risk register (top risks across the build)

| Risk | Likelihood | Impact | Mitigation | Owner phase |
|---|---|---|---|---|
| Integration/deploy discovered late | Med | High | Walking skeleton in P0; smoke-deploy to VM in early slack | P0 / P6 |
| Trust core (NLI + scoring) underperforms | Med | High | Scheduled at midpoint with slack both sides; adversarial set proves it; thresholds tuned + versioned | P2 / P5 |
| HU generation quality lags EN | Med | Med | Per-language TrustLayer; HU curriculum as native test bed | P3 |
| Local ML memory exceeds VM budget | Low | High | Models loaded once in worker; budget validated on VM spec early (`07` §7) | P2 / P6 |
| Frontend overruns (solo, backend-leaning) | Med | Med | Review UX only; no auth/settings; reuse highlight primitive | P4 |
| OpenAI cost / rate limits during demo | Low | Med | T1 NLI gating + Redis cache + pre-generated demo outputs | P2 / P6 |
| Solo bandwidth / illness | Med | High | 3-day end buffer; scope ladder (§10); freeze on 22 Sep | all |
| PDF extraction fragility on real papers | Med | Med | GROBID fallback pre-scoped; image-only detection warns not fails | P1 |

---

## 12. Definition of Done — MVP (competition-ready)

The MVP is complete when, on the public URL, a judge can:

1. Upload one of the sample research papers (EN or HU).
2. Watch it process through the async pipeline (visible progress).
3. Receive **five output types in both Hungarian and English**, each with an inline evidence trail.
4. Open any generated sentence and see its **source quote highlighted** in the original, with a sentence-type badge and confidence score.
5. See the **TrustLayer block or flag** an unsupported or numerically-wrong claim.
6. Accept / edit / flag elements and **export a bilingual PDF** with attribution.
7. Open the **Grafana dashboard** and see live eval + ops metrics.

…all reproducible from `docker compose up`, gated by CI (lint/type/test/**eval**), and backed by a versioned MLflow eval report meeting the [`05`](05-evaluation.md) MVP targets.

---

## 13. Beyond the MVP (AI Sprint Final, 9–10 Oct)

Should the project advance to the Sprint Final, the graduation paths are already documented, not invented under pressure: video **rendering**, multi-document synthesis, fine-tuned domain NLI, self-hosted vLLM, and the K8s/Terraform production topology — each already sketched in [`02` §7](02-architecture.md), [`03`](03-ai-pipeline.md), and [`07` §4](07-tech-stack.md). The MVP is the first slice of that production system; the Sprint deepens it along pre-planned seams.

---

*This closes the planning series (`01`–`08`). Execution begins at **Phase 0**.*
