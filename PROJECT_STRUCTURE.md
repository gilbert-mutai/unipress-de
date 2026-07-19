# UniPress DE — Project Structure

> Documentation of the repository layout, components, and data flow.
> **Reflects the codebase as of Phase 0** (the "walking skeleton"): the full
> production stack is scaffolded and runs end-to-end, but the domain pipeline
> (PDF parsing, claim extraction, TrustLayer, generation) is still stubbed —
> see the [Status & maturity](#status--maturity) section. Everything documented
> below is based on the actual committed files, not planned features.
>
> 🔄 **This is a living document — keep it current.** Whenever a change adds or
> removes a service, entry point, route, model, migration, env var, dependency,
> or top-level folder — or completes a phase — update the affected sections
> (tree, tables, env vars, data flow, status) in the *same* change. Base every
> entry on the real files; mark built vs. planned; never invent a file's purpose.

---

## 1. What this project is

UniPress DE turns a research paper (PDF) into bilingual (Hungarian + English)
science-communication materials — press release, lay article, social posts,
executive summary, video script — where **every claim is traced to its source
and audited for hallucination** before human review. See [`README.md`](README.md)
and [`docs/01-project-definition.md`](docs/01-project-definition.md) for the
product framing.

The repository is a **monorepo** with three deployable units (`api`, `worker`,
`frontend`), an observability/ops layer, a planning-docs series, and a dataset
manifest, all wired together by Docker Compose.

---

## 2. Visual directory tree

```
unipress-de/
├── api/                         # Python backend: FastAPI API + Celery worker (shared image)
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # ★ API entry point (FastAPI app)
│   │   ├── models.py            # Pydantic API contracts (JobCreate, JobRead, JobStatus)
│   │   ├── db_models.py         # SQLAlchemy tables (Job)
│   │   ├── api/                 # HTTP route handlers
│   │   │   ├── health.py        #   /health, /ready
│   │   │   └── jobs.py          #   POST /jobs, GET /jobs/{id}
│   │   ├── core/                # Cross-cutting infrastructure
│   │   │   ├── settings.py      #   Typed env config (pydantic-settings)
│   │   │   ├── db.py            #   SQLAlchemy engine + session + Base
│   │   │   ├── logging.py       #   structlog JSON logging
│   │   │   └── telemetry.py     #   OpenTelemetry tracing setup
│   │   ├── ports/               # Hexagonal interfaces (Protocols)
│   │   │   └── base.py          #   VectorStore, LLMGateway, Storage, TaskDispatch
│   │   ├── adapters/            # Concrete implementations of the ports
│   │   │   └── stubs.py         #   In-memory / echo / local-FS / Celery stubs
│   │   └── tasks/               # Async processing
│   │       ├── celery_app.py    #   ★ Celery worker entry point
│   │       └── chains.py        #   Demo pipeline (ingest→parse→embed→verify→finalize)
│   ├── alembic/                 # Database migrations
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0001_initial.py  #   Creates the `jobs` table
│   ├── alembic.ini
│   ├── tests/                   # pytest suite (SQLite-backed, no infra needed)
│   │   ├── conftest.py
│   │   ├── test_health.py
│   │   └── test_jobs.py
│   ├── pyproject.toml           # Python deps + tool config (ruff/mypy/pytest)
│   ├── uv.lock                  # Pinned, reproducible dependency lockfile
│   ├── Dockerfile               # Builds the shared api/worker image
│   └── .dockerignore
│
├── worker/
│   └── README.md                # Explains the worker shares api/'s image (no build yet)
│
├── frontend/                    # Next.js 14 (App Router) + TypeScript + Tailwind
│   ├── app/
│   │   ├── layout.tsx           #   Root layout + metadata
│   │   ├── page.tsx             #   ★ UI: submit a job, poll stage progress
│   │   └── globals.css          #   Tailwind entry + base styles
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── next.config.mjs          # Standalone output build
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── postcss.config.mjs
│   ├── next-env.d.ts
│   ├── Dockerfile               # Multi-stage standalone runtime image
│   └── .dockerignore
│
├── ops/                         # Observability & infra configs (mounted into containers)
│   ├── otel-collector/config.yaml   # OTLP receiver → Tempo
│   ├── prometheus/prometheus.yml    # Scrapes api /metrics
│   ├── tempo/tempo.yaml             # Trace storage
│   └── grafana/provisioning/datasources/datasources.yaml
│
├── docs/                        # Design/planning series (01–08) — source of truth
│   ├── 01-project-definition.md
│   ├── 02-architecture.md
│   ├── 03-ai-pipeline.md
│   ├── 04-content-outputs.md
│   ├── 05-evaluation.md
│   ├── 06-dataset-strategy.md
│   ├── 07-tech-stack.md
│   └── 08-dev-plan.md
│
├── data/
│   └── manifest.yaml            # Provenance + license for the sample corpus (PDFs gitignored)
│
├── sample_files_for_PR/         # Source PDFs — GITIGNORED, not committed
│
├── docker-compose.yml           # ★ Service topology (profiles: core|observability|ml|local-llm)
├── docker-compose.override.yml  # Local-dev port publishing
├── .env.example                 # Template for .env (real .env is gitignored)
├── .github/workflows/ci.yml     # CI: lint, type-check, test, build
├── .pre-commit-config.yaml      # Pre-commit hooks (ruff, mypy, hygiene)
├── .gitignore
├── README.md
└── PROJECT_STRUCTURE.md         # This file

# Present but gitignored (not part of the committed codebase):
#   DEIK_AI_Challenge_2026.md, prompt.md   → private planning inputs
#   .env                                    → local secrets
#   .claude/settings.local.json             → local Claude Code settings
#   api/.venv, frontend/node_modules, caches → generated
```

★ = application entry point.

---

## 3. Top-level layout by purpose

| Path | Type | Purpose | Why it matters |
|---|---|---|---|
| `api/` | Backend | FastAPI API + Celery worker (one shared image) | The whole domain/business logic lives here |
| `worker/` | Backend (doc only) | Placeholder for the future ML-heavy worker image | Currently reuses `api/`'s image; splits later (see below) |
| `frontend/` | Frontend | Next.js evidence-review UI | The product surface and demo |
| `ops/` | Infra config | OTel/Prometheus/Tempo/Grafana configs | Observability is a first-class, day-one concern |
| `docs/` | Documentation | Numbered design series `01`–`08` | The living source of truth; a competition asset |
| `data/` | Data | `manifest.yaml` (provenance/licensing) | Legal/attribution record for the corpus |
| `sample_files_for_PR/` | Data (ignored) | The 6 sample source PDFs | Input corpus; not committed (size + licensing) |
| repo root | Config | Compose, CI, env template, pre-commit | Ties the services into one runnable system |

---

## 4. Entry points

| Entry point | File | How it starts | Serves |
|---|---|---|---|
| **HTTP API** | [`api/app/main.py`](api/app/main.py) | `uvicorn app.main:app` | REST endpoints, `/metrics`, `/docs` |
| **Celery worker** | [`api/app/tasks/celery_app.py`](api/app/tasks/celery_app.py) | `celery -A app.tasks.celery_app.celery worker` | Executes async pipeline tasks |
| **Flower** | (same Celery app) | `celery -A app.tasks.celery_app.celery flower` | Queue/worker monitoring UI |
| **Migrations** | [`api/alembic/env.py`](api/alembic/env.py) | `alembic upgrade head` (one-shot `migrate` service) | Applies schema before api/worker boot |
| **Frontend** | [`frontend/app/page.tsx`](frontend/app/page.tsx) | `node server.js` (Next standalone) | The browser UI |

The `api`, `worker`, and `flower` **all run from the same Docker image**
(`api/Dockerfile`); only the start command differs. This is a deliberate Phase-0
choice documented in [`worker/README.md`](worker/README.md): the worker loads no
ML models yet, so a second image would be duplication. It graduates to its own
ML-heavy image once embeddings/NLI land.

---

## 5. Backend (`api/`) in detail

### 5.1 Application core (`app/core/`)

| File | Responsibility |
|---|---|
| [`settings.py`](api/app/core/settings.py) | Typed, env-driven config via `pydantic-settings`. `get_settings()` is `lru_cache`d. Invalid config fails fast at boot. |
| [`db.py`](api/app/core/db.py) | Creates the SQLAlchemy `Engine` and `SessionLocal`, defines the declarative `Base`, and provides `session_scope()` (worker transactions) and `get_db()` (FastAPI dependency). |
| [`logging.py`](api/app/core/logging.py) | Configures `structlog` to emit structured JSON logs at the configured level. |
| [`telemetry.py`](api/app/core/telemetry.py) | Installs an OpenTelemetry `TracerProvider`. OTLP export is **conditional** — only active when `OTEL_EXPORTER_OTLP_ENDPOINT` is set, so the `core` profile runs cleanly without a collector. Also instruments Celery. |

### 5.2 Domain models

| File | Type | Contents |
|---|---|---|
| [`db_models.py`](api/app/db_models.py) | SQLAlchemy ORM | `Job` table: `id` (UUID str PK), `status`, `stage`, `input_text`, `result`, `error`, `created_at`, `updated_at`. |
| [`models.py`](api/app/models.py) | Pydantic | API contracts: `JobStatus` (StrEnum: pending/processing/done/failed), `JobCreate` (input), `JobRead` (output, `from_attributes=True`). |

> Note: the richer domain contracts (`SourceSpan`, `Claim`, etc.) described in
> [`docs/03-ai-pipeline.md`](docs/03-ai-pipeline.md) are **not yet implemented** —
> Phase 0 has only the `Job` model.

### 5.3 Ports & adapters (hexagonal architecture)

The domain depends on **interfaces**, never concrete infrastructure, so backends
are swappable. This is the key architectural pattern.

| Port ([`ports/base.py`](api/app/ports/base.py)) | Purpose | Phase-0 adapter ([`adapters/stubs.py`](api/app/adapters/stubs.py)) | Graduation target |
|---|---|---|---|
| `VectorStore` | Embedding index | `InMemoryVectorStore` (substring match) | Chroma → Qdrant |
| `LLMGateway` | Text generation | `EchoLLM` (echoes prompt) | LiteLLM (OpenAI/Ollama) |
| `Storage` | Blob storage | `LocalStorage` (local FS) | MinIO / S3 |
| `TaskDispatch` | Async job dispatch | `CeleryTaskDispatch` | (Celery kept) |

Ports are `runtime_checkable` `Protocol`s, so `isinstance()` verifies an adapter
satisfies a port — [`tests/test_jobs.py`](api/tests/test_jobs.py) asserts exactly this.

### 5.4 API routes (`app/api/`)

| Method & path | Handler | Responsibility |
|---|---|---|
| `GET /health` | [`health.py`](api/app/api/health.py) | Liveness — process is up (no deps checked). Used by the container healthcheck. |
| `GET /ready` | `health.py` | Readiness — executes `SELECT 1` to confirm the DB is reachable. |
| `POST /jobs` | [`jobs.py`](api/app/api/jobs.py) | Creates a `Job` row (status `pending`), then enqueues the pipeline via `CeleryTaskDispatch`. Returns immediately (201). |
| `GET /jobs/{id}` | `jobs.py` | Reads current job state (404 if missing). The frontend polls this. |
| `GET /` | [`main.py`](api/app/main.py) | Service metadata. |
| `GET /metrics` | (Instrumentator) | Prometheus metrics, scraped by Prometheus. |
| `GET /docs` | (FastAPI) | OpenAPI/Swagger UI. |

The API is **thin by design**: validate → enqueue → read. All heavy work is
delegated to the worker.

### 5.5 Background jobs / queue (`app/tasks/`)

| File | Role |
|---|---|
| [`celery_app.py`](api/app/tasks/celery_app.py) | Defines the `celery` app. **Redis is both broker and result backend.** Configures JSON serialization, `task_acks_late`, `prefetch_multiplier=1`. Wires tracing so api→worker spans connect. |
| [`chains.py`](api/app/tasks/chains.py) | The demo pipeline. `start_pipeline(job_id)` builds a Celery **chain** over `STAGES = [ingest, parse, embed, verify]` then `finalize`. Each `run_stage` task updates the `Job` row (status/stage) in Postgres; `finalize` marks it `done`. This is a placeholder for the real pipeline in later phases. |

**Queue mechanics:** `POST /jobs` → `CeleryTaskDispatch.enqueue_pipeline` →
`start_pipeline` → `chain(...).apply_async()` → tasks run on the worker → each
stage persists progress → API reads reflect it.

### 5.6 Database, migrations & schema

- **ORM/engine:** [`app/core/db.py`](api/app/core/db.py) — synchronous SQLAlchemy 2.x with `psycopg` (Postgres 16).
- **Migrations:** Alembic. [`alembic/env.py`](api/alembic/env.py) pulls the URL and `Base.metadata` from the app (no duplicated config) and imports `db_models` so tables register.
- **Schema version `0001_initial`** ([`versions/0001_initial.py`](api/alembic/versions/0001_initial.py)) — creates the `jobs` table and `ix_jobs_status` index.
- Migrations run via a **one-shot `migrate` service** in Compose that must complete successfully before `api`/`worker` start (`service_completed_successfully`).

### 5.7 Tests (`api/tests/`)

| File | Covers |
|---|---|
| [`conftest.py`](api/tests/conftest.py) | Fixture that swaps the app's DB session for an **in-memory SQLite** engine and stubs `CeleryTaskDispatch.enqueue_pipeline` to run inline — so unit tests need **no Postgres, Redis, or Celery**. |
| [`test_health.py`](api/tests/test_health.py) | `/health`, `/ready`, `/` responses. |
| [`test_jobs.py`](api/tests/test_jobs.py) | Job create+read round-trip, 404 handling, and that the stub adapters satisfy their ports. |

**Testing strategy:** fast, hermetic unit/integration tests against SQLite with
external systems stubbed; CI also runs an ephemeral-service-free suite. Heavier
integration (real Postgres/Redis) and the eval harness arrive in later phases
(see [`docs/08-dev-plan.md`](docs/08-dev-plan.md) P5).

---

## 6. Frontend (`frontend/`)

A Next.js 14 App Router application (TypeScript + Tailwind).

| File | Role |
|---|---|
| [`app/page.tsx`](frontend/app/page.tsx) | Client component. Calls `POST /jobs`, then **polls** `GET /jobs/{id}` every ~700 ms, rendering a stage checklist (`queued → ingest → parse → embed → verify → done`) until a terminal state. This is the Phase-0 stand-in for the evidence-review dashboard. |
| [`app/layout.tsx`](frontend/app/layout.tsx) | Root HTML layout + page metadata. |
| [`app/globals.css`](frontend/app/globals.css) | Tailwind directives + base body styles. |
| [`next.config.mjs`](frontend/next.config.mjs) | `output: "standalone"` for a small runtime image. |
| [`Dockerfile`](frontend/Dockerfile) | Multi-stage: deps → build → minimal `node` runtime serving `server.js`. |

**API base URL:** the browser reads `NEXT_PUBLIC_API_BASE` (defaults to
`http://localhost:8000`). In production the frontend and API share one origin
behind Nginx (no CORS); in local dev CORS is enabled on the API (see below).

---

## 7. Configuration files

| File | Configures |
|---|---|
| [`.env.example`](.env.example) | Template listing every env var (see [Environment variables](#10-environment-variables)). Copy to `.env` (gitignored). |
| [`api/pyproject.toml`](api/pyproject.toml) | Python project: runtime deps, `dev` dependency group, and tool config for **ruff** (lint+format, line length 100), **mypy** (pydantic plugin), **pytest** (asyncio auto). |
| [`api/uv.lock`](api/uv.lock) | Fully pinned dependency graph for reproducible installs (`uv sync --frozen`). |
| [`frontend/package.json`](frontend/package.json) + [`pnpm-lock.yaml`](frontend/pnpm-lock.yaml) | Frontend deps and scripts (`dev`/`build`/`start`/`lint`), pinned via pnpm. |
| [`frontend/tsconfig.json`](frontend/tsconfig.json), [`tailwind.config.ts`](frontend/tailwind.config.ts), [`postcss.config.mjs`](frontend/postcss.config.mjs) | TypeScript, Tailwind, PostCSS. |
| [`.pre-commit-config.yaml`](.pre-commit-config.yaml) | Pre-commit hooks: ruff (fix+format on `api/`), mypy on `app/`, plus hygiene hooks (EOF, trailing whitespace, YAML/large-file/merge-conflict checks). |
| [`.gitignore`](.gitignore) | Excludes secrets, venvs, `node_modules`, ML artifacts, PDFs, generated caches. |

---

## 8. Docker, Compose & infrastructure

### 8.1 Compose topology

[`docker-compose.yml`](docker-compose.yml) defines all services, grouped by
**profiles** so you run only what you need:

| Profile | Services | Notes |
|---|---|---|
| `core` | `postgres`, `redis`, `migrate`, `api`, `worker`, `flower`, `frontend` | The application. |
| `observability` | `otel-collector`, `prometheus`, `tempo`, `grafana` | Opt-in monitoring stack. |
| `ml` | `mlflow` | Eval/experiment tracking (used from Phase 5). |
| `local-llm` | `ollama` | Optional local-LLM path for the privacy demo. |

Key details:
- A shared `x-app-env` anchor injects `DATABASE_URL`, `REDIS_URL`, and OTel vars into `api`/`worker`/`migrate`/`flower`.
- **Health-gated startup:** `api`/`worker` wait for `postgres`+`redis` healthy and `migrate` completed.
- Named volumes persist Postgres, Redis (AOF), Tempo, Grafana, MLflow, and Ollama data.
- [`docker-compose.override.yml`](docker-compose.override.yml) publishes host ports for local dev (api `8000`, frontend `3000`, flower `5555`, prometheus `9090`, grafana `3001`, tempo `3200`, mlflow `5000`) and sets `NEXT_PUBLIC_API_BASE`.

### 8.2 Images

| Dockerfile | Builds | Base |
|---|---|---|
| [`api/Dockerfile`](api/Dockerfile) | Shared api/worker/flower/migrate image; installs deps with `uv` in two cached layers. | `python:3.12-slim` |
| [`frontend/Dockerfile`](frontend/Dockerfile) | Next.js standalone runtime. | `node:20-alpine` |

### 8.3 Observability configs (`ops/`)

| File | Configures |
|---|---|
| [`ops/otel-collector/config.yaml`](ops/otel-collector/config.yaml) | Receives OTLP (gRPC 4317 / HTTP 4318), batches, exports **traces → Tempo**. |
| [`ops/prometheus/prometheus.yml`](ops/prometheus/prometheus.yml) | Scrapes the api's `/metrics` and itself (15s interval). |
| [`ops/tempo/tempo.yaml`](ops/tempo/tempo.yaml) | Single-binary Tempo with local trace storage, OTLP gRPC ingest, 24h retention. |
| [`ops/grafana/.../datasources.yaml`](ops/grafana/provisioning/datasources/datasources.yaml) | Provisions Prometheus (default) + Tempo datasources. |

> There is **no Kubernetes, Terraform, or Nginx config in the repo yet.** The
> production deployment (Angani VM, Nginx + Certbot TLS, backups) is *specified*
> in [`docs/07-tech-stack.md`](docs/07-tech-stack.md) §9 but not yet codified —
> it lands in Phase 6.

### 8.4 CI/CD

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on push/PR to
`master`/`dev`:

- **backend job:** `uv sync --frozen` → `ruff check` → `ruff format --check` → `mypy app` → `pytest`.
- **frontend job:** `pnpm install --frozen-lockfile` → `tsc --noEmit` → `pnpm build`.

The eval-gate and deploy steps referenced in the plan are future (Phase 5/6).

---

## 9. Authentication & authorization

**None yet.** There is no auth/authz layer in the Phase-0 codebase — no login,
sessions, tokens, or role checks. Per [`docs/02-architecture.md`](docs/02-architecture.md)
§8, SSO/auth and multi-tenancy are explicitly a *production graduation*, not an
MVP feature. The only access controls today are network-level (intended: data
services stay on the internal Docker network; Grafana behind admin auth).

---

## 10. Environment variables

Defined in [`.env.example`](.env.example) and consumed by
[`api/app/core/settings.py`](api/app/core/settings.py) and Compose. **No secret
values are stored in the repo** — `.env` is gitignored.

| Variable | Used by | Purpose |
|---|---|---|
| `APP_ENV` | api/worker | Environment name (e.g. development). |
| `LOG_LEVEL` | api/worker | structlog level. |
| `OTEL_SERVICE_NAME` | api/worker | Service name on traces. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | api/worker | OTLP collector endpoint; **empty disables trace export**. |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | postgres, `DATABASE_URL` | DB credentials/name (**secret** — set in `.env`). |
| `DATABASE_URL` | api/worker/migrate | Full SQLAlchemy connection string (assembled in Compose). |
| `REDIS_URL` | api/worker | Celery broker + result backend. |
| `GRAFANA_ADMIN_PASSWORD` | grafana | Grafana admin password (**secret**). |
| `OPENAI_API_KEY` | api (future) | LLM key; unused until the generation phase (**secret**). |
| `NEXT_PUBLIC_API_BASE` | frontend (browser) | API base URL for browser calls. |
| `cors_origins` (setting) | api | Allowed CORS origins; defaults to `http://localhost:3000` for local dev. |

---

## 11. External integrations & third-party services

| Service | Status | Where |
|---|---|---|
| **PostgreSQL 16** | Active | Relational store (jobs, later claims/spans). |
| **Redis 7** | Active | Celery broker + result backend. |
| **OpenTelemetry Collector / Tempo / Prometheus / Grafana** | Active (observability profile) | Traces, metrics, dashboards. |
| **MLflow** | Scaffolded (ml profile) | Eval/experiment tracking (Phase 5). |
| **Ollama** | Scaffolded (local-llm profile) | Optional local LLM. |
| **OpenAI (via LiteLLM)** | Planned | Generation; key placeholder present, no client code yet. |
| **Chroma, BGE-M3, DeBERTa, PyMuPDF, GROBID** | Planned | Named in `docs/07`; not yet in `pyproject.toml`. |

---

## 12. Documentation & data

- [`docs/01`–`08`](docs/) — the numbered design series (definition → architecture → AI pipeline → outputs → evaluation → dataset → tech stack → dev plan). These are the **authoritative design record** and are kept in sync with the code as it's built.
- [`data/manifest.yaml`](data/manifest.yaml) — provenance, authorship, DOI, and license for each of the 6 sample documents. The **PDFs themselves live in `sample_files_for_PR/` and are gitignored** (size + licensing); only the manifest is committed.

---

## 13. Architecture & data flow

```mermaid
flowchart LR
    U[Browser · Next.js] -->|POST /jobs| API[FastAPI api · thin]
    API -->|INSERT Job pending| PG[(Postgres)]
    API -->|enqueue chain| RED[(Redis broker)]
    RED --> WK[Celery worker]
    WK -->|per-stage UPDATE| PG
    U -->|poll GET /jobs/id| API
    API -->|read Job| PG
    API -. traces/metrics .-> OTEL[OTel Collector]
    WK  -. traces .-> OTEL
    OTEL --> TEMPO[(Tempo)]
    API -->|/metrics| PROM[(Prometheus)]
    TEMPO --> GRAF[Grafana]
    PROM --> GRAF
```

**Request/data flow (current):**
1. The browser submits a job (`POST /jobs`). The API writes a `pending` `Job` row and enqueues a Celery chain, returning immediately.
2. The worker executes the chain; each stage updates the `Job`'s `status`/`stage` in Postgres.
3. The browser polls `GET /jobs/{id}` and renders progress until `done`.
4. Throughout, the API and worker emit traces (→ OTel Collector → Tempo) and the API exposes metrics (→ Prometheus), both visualized in Grafana.

This exercises the **entire production path** (HTTP → queue → worker → DB →
read-back → observability) with a trivial payload. Later phases replace the demo
stages with real parsing, claim extraction, retrieval, generation, and the
TrustLayer — **without changing this skeleton**, because each concern sits behind
a port.

---

## 14. Status & maturity

| Layer | State |
|---|---|
| Repo scaffolding, Compose, CI, ports/adapters | **Implemented & verified** (Phase 0) |
| Job model, API, Celery demo chain, migrations | **Implemented & verified** |
| Frontend job-submit/poll shell | **Implemented** |
| Observability wiring | **Implemented** (trace-in-Tempo confirmation deferred into Phase 1) |
| PDF parsing, claim store, retrieval | **Not started** (Phase 1) |
| Generation + TrustLayer | **Not started** (Phase 2) |
| Bilingual outputs, review dashboard, eval harness, deployment | **Not started** (Phases 3–6) |

No files in the committed tree appear **dead or deprecated** — everything present
is part of the active Phase-0 skeleton. See
[`docs/08-dev-plan.md`](docs/08-dev-plan.md) for the phase roadmap.
