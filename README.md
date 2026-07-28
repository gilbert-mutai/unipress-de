# UniPress DE

> **Trustworthy, traceable science communication — at 10× speed.**
> DEIK.AI Challenge 2026 · Category 2.C (AI-Assisted PR Content Generation)

UniPress DE turns a research paper (PDF) into publication-ready, **bilingual (Hungarian + English)** communication materials — press release, lay article, social posts, executive summary, and a 60-second video script — where **every factual claim is linked to its exact source and audited for hallucination before a human ever sees it.**

Generic AI tools generate fluent, confident text with no evidence trail, so a press officer can't trust the output without re-reading the whole paper. UniPress DE is verification-first: it decomposes the paper into quote-anchored claims, generates content structurally bound to those claims, and independently checks every generated sentence against its cited evidence.

---

## Live demo

The system runs on a public HTTPS host — a single origin behind nginx, so the app, the API and the dashboard all share one domain.

| | URL |
|---|---|
| **The app** — upload → generate → review evidence → export | **<https://unipress.gilbertmutai.com/>** |
| **Trust & Ops dashboard** — live eval + ops metrics (Grafana, read-only) | <https://unipress.gilbertmutai.com/grafana/d/unipress-overview> |
| **API reference** — interactive Swagger UI | <https://unipress.gilbertmutai.com/api/docs> |
| API reference — ReDoc · raw schema | [`/api/redoc`](https://unipress.gilbertmutai.com/api/redoc) · [`/api/openapi.json`](https://unipress.gilbertmutai.com/api/openapi.json) |
| Health probes — liveness · readiness (checks the DB) | [`/api/health`](https://unipress.gilbertmutai.com/api/health) · [`/api/ready`](https://unipress.gilbertmutai.com/api/ready) |

Every API route lives under `/api` (nginx strips the prefix before proxying). Only 80/443 are published — Prometheus, Flower, MLflow and Tempo stay on the internal Docker network and are reachable in local dev only (see [Quickstart](#quickstart)).

## Why it's different

- **Evidence-linked claims** — every generated sentence traces back to a page / section / verbatim quote.
- **TrustLayer** — each sentence is typed (*explicit fact · reasonable interpretation · rhetorical framing · unsupported*), grounded via an NLI + LLM-judge check, and confidence-scored; unsupported or numerically-wrong claims are blocked or flagged.
- **Bilingual scientific rewriting** (HU↔EN) — audience-adapted, not literal translation.
- **Human-in-the-loop review dashboard** — accept / edit / flag each element with the source shown alongside.
- **Multi-audience fan-out** from one verified claim store — write the facts once, render for five audiences.

## How it works

```mermaid
flowchart LR
    P[Paper] --> PARSE[Parse + spans]
    PARSE --> EX[Claim extraction]
    EX --> QG{Quote found<br/>in source?}
    QG -->|no| DROP[Reject claim]
    QG -->|yes| CS[(Claim store)]
    PARSE --> EMB[Chunk + embed] --> VS[(Vector store)]
    CS & VS --> GEN[Claim-bound generation]
    GEN --> TL[TrustLayer verify]
    TL --> SCORE[Verdict + confidence]
    SCORE --> REV[Human review] --> OUT[Bilingual output]
```

## Tech stack (summary)

FastAPI · Celery + Redis · PostgreSQL + Alembic · Chroma (vectors) · BGE-M3 embeddings · DeBERTa NLI · LiteLLM → OpenAI (Ollama optional) · Next.js · OpenTelemetry / Prometheus / Grafana · Docker Compose. Full rationale in [`docs/07-tech-stack.md`](docs/07-tech-stack.md).

## Quickstart

> _Populated as the build lands (Phase 0). The whole system comes up with a single command:_

```bash
cp .env.example .env        # add your OpenAI key
docker compose --profile core up
# add --profile observability for the Grafana/OTel stack
```

Locally the services publish their own ports (unlike production, where only nginx is exposed):

| URL | Service |
|---|---|
| <http://localhost:3000> | Frontend |
| <http://localhost:8000/docs> | API + Swagger UI |
| <http://localhost:3001> | Grafana (`admin` / `$GRAFANA_ADMIN_PASSWORD`) — `observability` profile |
| <http://localhost:9090> | Prometheus — `observability` profile |
| <http://localhost:3200> | Tempo (traces) — `observability` profile |
| <http://localhost:5555> | Flower (Celery queue inspector) |
| <http://localhost:5000> | MLflow (eval runs) — `ml` profile |

## Documentation

The design is fully specified before code — the planning series lives in [`docs/`](docs/):

| # | Doc | Contents |
|---|---|---|
| 01 | [Project Definition](docs/01-project-definition.md) | Problem, users, pitch, scope |
| 02 | [System Architecture](docs/02-architecture.md) | Components, MVP/production split |
| 03 | [AI Pipeline & Anti-Hallucination](docs/03-ai-pipeline.md) | Data contracts, TrustLayer algorithm |
| 04 | [Content Generation Spec](docs/04-content-outputs.md) | The five output types |
| 05 | [Evaluation Framework](docs/05-evaluation.md) | Faithfulness, hallucination, readability metrics |
| 06 | [Dataset & Testing Strategy](docs/06-dataset-strategy.md) | Gold set, adversarial set, corpus |
| 07 | [Technology Stack](docs/07-tech-stack.md) | Justified tech choices |
| 08 | [MVP Development Plan](docs/08-dev-plan.md) | Phased build to the deadline |

## Dataset & licensing

The primary corpus is the challenge's official sample materials — four CC BY 4.0 research papers and two University of Debrecen curricula. Provenance and licensing per document are recorded in [`data/manifest.yaml`](data/manifest.yaml). Source PDFs are not committed to the repo. Attribution (title, authors, DOI, license) is shown on every generated output.

## Status

Planning complete (docs 01–08); implementation in progress on `dev`, starting at Phase 0 of the [development plan](docs/08-dev-plan.md). Demo deadline: **25 September 2026**.
