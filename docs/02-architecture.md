# UniPress DE — System Architecture

> **DEIK.AI Challenge 2026 · Category 2.C** · Companion to [`01-project-definition.md`](01-project-definition.md)
> Build mode: Solo · LLM strategy: Hybrid (OSS core + swappable hosted LLM) · Deploy: Docker Compose

---

## 0. Design principles

Every choice below serves five constraints, in priority order:

1. **Trustworthy output** — the system's whole reason to exist is verifiable, evidence-linked content. Architecture optimizes for traceability first, cleverness second.
2. **Demoable in 3 minutes** — the happy path (paper in → verified outputs out, with evidence side-by-side) must be fast and visually legible.
3. **Solo-buildable by 25 Sept** — favor managed simplicity; cut anything not on the critical path.
4. **Locally deployable** — supports the "data protection / on-prem" narrative; nothing hard-wired to a single vendor.
5. **MLOps-ready, not MLOps-heavy** — structured for observability/eval from day one, but we only turn on what earns its keep.

**North-star rule:** *No claim reaches the final output without a source span attached to it.* This is enforced structurally, not by prompt-hoping.

---

## 1. High-level architecture

```mermaid
flowchart TD
    U[Comms officer / researcher] -->|upload paper| FE[Next.js Frontend]
    FE <-->|REST| API[FastAPI Backend]

    subgraph Core["UniPress Core"]
        API --> ING[Ingestion & Parsing]
        ING --> CLM[Claim & Fact Extraction]
        CLM --> CS[(Claim Store<br/>Postgres)]
        ING --> CHUNK[Chunking + Embeddings]
        CHUNK --> VDB[(Vector DB<br/>Chroma)]
        API --> GEN[Content Generation<br/>RAG + citation-aware]
        CS --> GEN
        VDB --> GEN
        GEN --> TL[TrustLayer<br/>verify + classify + score]
        CS --> TL
        TL --> REV[Human Review Dashboard]
        REV --> OUT[Bilingual Output Renderer]
    end

    GEN <-->|generation| LLM[LLM Gateway<br/>swappable]
    TL <-->|NLI / grounding| LLM
    LLM -.-> HOSTED[Hosted frontier LLM]
    LLM -.-> LOCAL[Local OSS LLM]

    API --> OBS[Observability<br/>logs + traces + eval metrics]
```

**Plain English:** A user uploads a paper through the Next.js UI. FastAPI orchestrates a pipeline: the paper is parsed, its factual claims are extracted into a **Claim Store** (each with a source span), and its text is chunked and embedded into a **Vector DB**. When the user requests outputs, the **Generation** stage produces content grounded in retrieved chunks and the claim store. **TrustLayer** then checks every generated sentence against the source, classifies it, and scores confidence. The result goes to a **Review Dashboard** where the officer accepts/edits/flags, and finally the **Output Renderer** produces the bilingual deliverables. A single **LLM Gateway** abstracts whether generation runs on a hosted or local model.

---

## 2. Component architecture

For each component: **purpose · why needed · recommended tech · alternatives · trade-offs**. Components not justified for the solo MVP are listed in §7 (Deliberate exclusions).

### 2.1 Frontend — Review & Demo UI
- **Purpose:** Upload a paper, trigger generation, and — the money shot — show each generated claim next to its source evidence, with accept/edit/flag controls.
- **Why needed:** The human-in-the-loop review *is* the product's trust story and the demo's centerpiece. A CLI can't sell this.
- **Recommended:** **Next.js + React + Tailwind** (your stack). Server-side calls to FastAPI.
- **Alternatives:** Streamlit/Gradio (faster to build, weaker UX, less credible on video); plain SPA.
- **Trade-offs:** Next.js costs more time than Streamlit but produces the polished, split-view evidence UI that wins on camera. Worth it.

### 2.2 API / Orchestration — FastAPI
- **Purpose:** Coordinate the pipeline, expose REST endpoints, manage jobs.
- **Why needed:** Central control plane; clean seam between UI and AI.
- **Recommended:** **FastAPI + Pydantic v2** (typed contracts everywhere — critical for structured outputs).
- **Alternatives:** Flask (less async/typing), Node/Nest (splits your AI code from Python ecosystem — avoid).
- **Trade-offs:** FastAPI async + Pydantic gives typed, validated structured outputs for free — directly supports the anti-hallucination design.

### 2.3 Ingestion & Structure-aware Parsing
- **Purpose:** PDF → clean, structured text with **positional metadata** (page, section, bounding box) so claims can point back to exact locations.
- **Why needed:** Evidence-linking is impossible without knowing *where* text came from. This is foundational, not optional.
- **Recommended:** **Docling** (IBM, OSS) or **PyMuPDF (fitz)** for layout + coordinates; **GROBID** for scientific-PDF structure (title/abstract/sections/references) if we need robust academic parsing.
- **Alternatives:** unstructured.io (heavier), pdfplumber (tables good, layout weaker), raw pypdf (no layout).
- **Trade-offs:** GROBID is purpose-built for papers and gives excellent section/reference structure but adds a Java service. Start with PyMuPDF/Docling; add GROBID if section detection is weak. **OCR (Tesseract) deferred** — assume born-digital PDFs for MVP.

### 2.4 Claim & Fact Extraction
- **Purpose:** Turn the paper into a list of atomic **claims**, each with `{text, type, source_span}`. This is the knowledge representation.
- **Why needed:** The differentiator. Generation is constrained to these claims; TrustLayer verifies against them. Without it we're just another summarizer.
- **Recommended:** **LLM-based extraction with a strict JSON schema** (via the gateway), each claim tagged with the supporting quote + offsets. Store atomic, checkable statements.
- **Alternatives:** Pure OpenIE / spaCy triples (brittle on scientific prose); rule-based (won't generalize).
- **Trade-offs:** LLM extraction is flexible but must be schema-constrained and validated (reject claims whose quote isn't found in the source text — a cheap, powerful guardrail).

### 2.5 Claim Store (structured knowledge)
- **Purpose:** Canonical record of every claim + provenance; the join key between generation and verification.
- **Why needed:** Provenance must be queryable and durable, not held in a prompt.
- **Recommended:** **PostgreSQL** (JSONB for spans) for relational data + provenance; vectors live separately in Chroma (§2.7).
- **Alternatives:** SQLite (fine for MVP, but Postgres has a cleaner production story); a graph DB (overkill now).
- **Trade-offs:** Postgres slightly heavier than SQLite but is the durable, queryable home for claims/spans/metrics and a natural production path.

### 2.6 Chunking + Embeddings
- **Purpose:** Make the paper retrievable for RAG.
- **Why needed:** Generation and verification both retrieve supporting passages.
- **Recommended:** Section-aware chunking (respect the parsed structure); embeddings via **BGE-m3** or **multilingual-e5** (both strong, **multilingual → supports HU + EN**).
- **Alternatives:** OpenAI/Cohere embeddings (quality, but breaks "local" story), naive fixed-size chunking (loses structure).
- **Trade-offs:** Multilingual OSS embeddings keep the local-deployability narrative intact and handle both languages with one model.

### 2.7 Vector Database
- **Purpose:** Semantic retrieval of chunks.
- **Why needed:** Core of RAG.
- **Recommended:** **Chroma** (dedicated vector store, run as its own service or in persistent mode).
- **Why:** The builder has prior hands-on Chroma experience — for a solo build against a deadline, familiarity lowers delivery risk and speeds iteration. Open-source, local, clean Python API with metadata filtering.
- **Alternatives:** pgvector (keeps everything in one Postgres service, but a new tool for the builder); Qdrant (excellent, no prior experience). 
- **Trade-offs:** Adds a second data service alongside Postgres — accepted, because the confidence/speed gain from a known tool outweighs the extra container on a solo timeline. Retrieval accesses vectors through a thin `VectorStore` interface, so a later swap to Qdrant is an adapter change, not a rewrite.

### 2.8 Content Generation (RAG, citation-aware)
- **Purpose:** Produce each output type (press release, article, social, exec summary, video script) grounded in retrieved chunks + claim store, emitting **structured output where each sentence carries claim IDs**.
- **Why needed:** The generator; audience-adaptive rendering of verified facts.
- **Recommended:** LLM via gateway with **per-output-type prompt templates + JSON schema** binding sentences → claim IDs. Retrieval provides context; claim store constrains facts.
- **Alternatives:** Free-form generation then post-hoc citation matching (weaker linkage); fine-tuned model (out of scope for MVP — revisit for Sprint).
- **Trade-offs:** Structured, claim-bound generation is more prompt engineering up front but makes verification tractable and evidence-linking native.

### 2.9 TrustLayer — Verification, Classification, Scoring
- **Purpose:** For every generated sentence: (a) retrieve its cited source span, (b) check entailment (does the source actually support it?), (c) classify as *explicit fact / reasonable interpretation / rhetorical framing / unsupported*, (d) assign a confidence score. Block or flag unsupported claims.
- **Why needed:** This is the soul of the project and the credibility play for an academic jury.
- **Recommended:** **Two-tier check** — (1) fast NLI model (e.g. a fine-tuned DeBERTa-MNLI or `bge-reranker` grounding score) for entailment; (2) LLM-as-judge for classification + edge cases. Combine into a confidence score. Also run **claim-coverage** (did we omit important facts?).
- **Alternatives:** LLM-only judging (simpler, but slower/pricier and less defensible); metric-only (RAGAS faithfulness) — good for eval, thin for per-sentence UX.
- **Trade-offs:** Two-tier balances cost/latency/rigor and gives a defensible, explainable verdict per sentence. This is where to spend engineering depth.

### 2.10 Human Review Dashboard
- **Purpose:** Present outputs with per-sentence verdicts + evidence; let the officer accept/edit/flag; capture decisions (also = eval data + the "human satisfaction" metric).
- **Why needed:** Human-in-the-loop is both a trust guarantee and a demo highlight.
- **Recommended:** Part of the Next.js app; split view (generated text ↔ highlighted source).
- **Trade-offs:** Building the evidence-linked UI well is time-consuming but is literally the winning demo moment.

### 2.11 Bilingual Output Renderer
- **Purpose:** Produce final HU + EN deliverables in clean formats (Markdown/HTML/PDF; video script as timed text).
- **Why needed:** The tangible product.
- **Recommended:** Template-based rendering (Jinja2 → Markdown/HTML; WeasyPrint for PDF). Generate per language with the same claim constraints (not blind machine translation — regenerate constrained to claims in the target language).
- **Trade-offs:** Regenerate-per-language costs more calls but preserves factual fidelity across languages (a genuine differentiator vs. translate-after-the-fact).

### 2.12 LLM Gateway (swappable model layer)
- **Purpose:** Single abstraction over generation + judging models; config-driven choice of hosted vs. local.
- **Why needed:** The hybrid strategy depends on this; also enables cost/latency control and prevents vendor lock-in.
- **Recommended:** Thin internal client or **LiteLLM** to unify APIs; hosted frontier model for quality, **Ollama / vLLM** for local OSS models.
- **Alternatives:** Hard-code one provider (kills the hybrid narrative — avoid).
- **Trade-offs:** A small abstraction cost now buys the entire "locally deployable, no lock-in" story and easy A/B of models in eval.

### 2.13 Observability & Evaluation hooks
- **Purpose:** Log every stage, trace latency/cost per request, capture eval metrics (faithfulness, hallucination rate, coverage, reviewer decisions).
- **Why needed:** "Evaluate seriously, not by vibes" (your brief) + MLOps-ready posture.
- **Recommended (MVP):** Structured logging + a metrics table in Postgres + a simple dashboard page. **(Competition+):** OpenTelemetry traces; **(Production):** Prometheus + Grafana, MLflow for eval runs.
- **Trade-offs:** Keep it light for MVP; the *hooks* matter more than the heavy stack now.

---

## 3. Data flow (request lifecycle)

```mermaid
sequenceDiagram
    actor User
    participant FE as Next.js
    participant API as FastAPI
    participant ING as Ingestion
    participant CLM as Claim Extractor
    participant DB as Postgres (claims+vectors)
    participant GEN as Generator
    participant TL as TrustLayer
    participant LLM as LLM Gateway

    User->>FE: Upload paper + choose outputs/languages
    FE->>API: POST /documents
    API->>ING: parse PDF (text + spans)
    ING->>CLM: structured sections
    CLM->>LLM: extract atomic claims (JSON schema)
    LLM-->>CLM: claims + quotes
    CLM->>DB: store claims (reject if quote not in source)
    ING->>DB: store chunks + embeddings
    API-->>FE: doc ready (claim count, sections)

    User->>FE: Generate outputs
    FE->>API: POST /generate
    API->>GEN: retrieve + build prompt (claim-bound)
    GEN->>LLM: generate (sentences → claim IDs)
    LLM-->>GEN: structured draft
    GEN->>TL: verify each sentence
    TL->>LLM: NLI + judge (grounding)
    TL-->>API: verdicts + confidence + flags
    API-->>FE: outputs + evidence + verdicts
    User->>FE: Accept / edit / flag → export HU + EN
```

---

## 4. AI pipeline (the trust-critical path)

```mermaid
flowchart LR
    A[Source paper] --> B[Structure-aware parse<br/>+ source spans]
    B --> C[Atomic claim extraction<br/>quote-verified]
    C --> D[(Claim store)]
    B --> E[Chunk + embed]
    E --> F[(Vector store)]
    D & F --> G[Claim-bound generation]
    G --> H{TrustLayer}
    H -->|explicit fact| I[Keep]
    H -->|interpretation| J[Keep + label]
    H -->|rhetorical| K[Keep + label]
    H -->|unsupported| L[Block / flag for human]
    I & J & K --> M[Human review]
    L --> M
    M --> N[Bilingual render HU/EN]
```

**Hallucination controls, layered (defense in depth):**
1. **Extraction guardrail** — reject any claim whose supporting quote isn't literally found in the source.
2. **Claim-bound generation** — the model writes *from* the claim store, not from memory.
3. **Structured sentence→claim binding** — every sentence must cite a claim ID or be marked rhetorical.
4. **TrustLayer entailment check** — NLI verifies the cited span actually supports the sentence.
5. **Classification + confidence** — unsupported/low-confidence content is blocked or flagged.
6. **Human review** — final gate, and the decisions feed evaluation.

---

## 5. Deployment architecture

```mermaid
flowchart TD
    subgraph Docker Compose
        FEc[frontend: next.js]
        APIc[api: fastapi]
        DBc[(postgres:<br/>claims/spans/metrics)]
        CHc[(chroma:<br/>vectors)]
        OLc[ollama: local LLM optional]
        GRc[grobid: optional]
    end
    FEc --> APIc
    APIc --> DBc
    APIc --> CHc
    APIc -. local .-> OLc
    APIc -. hosted .-> EXT[Hosted LLM API]
    APIc -. optional .-> GRc
```

- **MVP:** `docker-compose up` brings the whole system up locally — one command, great for the demo and the "locally deployable" claim.
- **Competition:** same compose, optionally deployed to a single cloud VM for a public demo URL.
- **Production:** Kubernetes + Terraform (your strengths), managed Postgres, autoscaled model serving (vLLM), object storage for docs. **Deferred — not built for MVP.**

---

## 6. Security & data-handling architecture

- **Secrets:** `.env` (git-ignored) → env vars; no keys in code. Production: a secrets manager.
- **Data minimization / privacy:** documents processed locally; hybrid mode allows **fully local inference** so sensitive/unpublished papers never leave the machine — a concrete privacy story for the jury.
- **Licensing safety:** default corpus = open-access only (arXiv/DOAJ/PMC); uploads are user-owned; nothing copyrighted committed (see `.gitignore`). Provenance stored per document.
- **Input safety:** validate file type/size; treat PDF text as untrusted; guard against prompt-injection embedded in documents (system prompts isolate source text; TrustLayer catches injected "facts" with no grounding).
- **Auditability:** every output carries its evidence trail + model/version used — reproducibility and accountability.

---

## 7. Deliberate exclusions (what a solo MVP does NOT build)

Per your brief — *only include what's justified.* Explicitly cut for MVP, with rationale:

| Excluded | Why not now | When to add |
|---|---|---|
| OCR (Tesseract) | Assume born-digital PDFs; OCR is a rabbit hole | If scanned docs matter (Sprint) |
| Qdrant / production vector infra | Chroma is enough at demo scale (builder-familiar) | Multi-tenant corpus (production) |
| Fine-tuning / QLoRA | Prompt + RAG + verification gets us there; training is time-expensive | If eval shows a specific gap (Sprint) |
| Full video *rendering* (TTS + assembly) | High effort, low marginal jury value vs. script | Stretch module / Sprint |
| Kubernetes, Prometheus/Grafana, MLflow | Compose + light logging is enough to demo | Production hardening |
| Multi-document / cross-paper synthesis | Single-paper is a cleaner, stronger demo | Sprint feature |
| Auth / multi-user | Single-user demo; adds no jury value | Production |

**Video note:** MVP delivers a polished **video script** (timed, scene-by-scene). Actual video generation (TTS voiceover + captioned assembly) is a clearly-scoped *stretch* module — impressive on camera, but never at the expense of the trust core.

---

## 8. MVP / Competition / Production split (summary)

| Capability | MVP | Competition | Production |
|---|:--:|:--:|:--:|
| PDF parse + spans | ✅ | ✅ | ✅ + OCR |
| Claim extraction (quote-verified) | ✅ | ✅ | ✅ |
| RAG generation (claim-bound) | ✅ | ✅ | ✅ |
| TrustLayer (NLI + judge + score) | ✅ | ✅ ➕ deeper | ✅ |
| Evidence-linked review UI | ✅ | ✅ polished | ✅ |
| Outputs: press/article/social/exec/script | ✅ | ✅ | ✅ |
| Bilingual HU + EN | ✅ | ✅ | ✅ + more langs |
| Evaluation harness | basic | ✅ full | ✅ CI-gated |
| Local + hosted LLM (gateway) | ✅ | ✅ | ✅ vLLM |
| Video rendering | — | stretch | ✅ |
| Deploy | Compose | Compose+VM | K8s+Terraform |
| Observability | logs+table | +OTel | Prom/Grafana/MLflow |

---

## 9. Open decisions to resolve in the Tech Stack phase

1. Parser: PyMuPDF/Docling alone vs. + GROBID (decide after testing on 3–5 real papers).
2. Embedding model: BGE-m3 vs. multilingual-e5 (bench on HU + EN retrieval).
3. NLI model choice + threshold for the TrustLayer entailment tier.
4. Hosted LLM provider for the generation tier (quality vs. cost) via the gateway.
5. Confidence-score formula (how NLI + judge combine into one number).

## Next phase

**AI Pipeline & Anti-Hallucination Design** (`03-ai-pipeline.md`) — deep dive on claim extraction schema, the sentence↔claim binding format, and the exact TrustLayer verdict/scoring algorithm.
