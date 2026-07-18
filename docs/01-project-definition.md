# UniPress DE — Project Definition

> **DEIK.AI Challenge 2026 · Category 2.C — AI-Assisted PR Content Generation**
> Status: Definition locked · Build mode: Solo · LLM strategy: Hybrid (open-source core + swappable hosted frontier LLM)
> Demo deadline: 25 September 2026 · Possible AI Sprint Final: 9–10 October 2026

---

## 1. Name

**UniPress DE**

Working name; signals *university + press + Debrecen*. Alternatives considered: EvidenceDesk, ClaimWire, Veritas Newsroom.

## 2. One-sentence pitch

UniPress DE turns a research paper into publication-ready, bilingual (HU/EN) communication materials — press release, public article, social posts, and a video script — where **every factual claim is linked to its exact source and audited for hallucination** before a human ever sees it.

## 3. Problem statement

Universities and research institutes generate a constant stream of valuable findings, but the "last mile" — translating dense papers into accurate, public-facing communication — is a manual bottleneck owned by a handful of overworked comms staff. The result: most research is never publicized, and when it is, non-expert writers risk **factual drift and overclaiming**. Generic AI tools make this *worse*, not better: they generate fluent, confident text with no traceability, so a press officer can't trust the output without re-reading the whole paper — which defeats the purpose.

## 4. Current pain point

- A single press release from a technical paper takes a skilled writer **hours** (read → understand → simplify → verify → translate).
- Non-expert writers introduce errors; experts don't have time to write for the public.
- Bilingual output (HU + EN) doubles the effort and doubles the error surface.
- Off-the-shelf LLMs **hallucinate** and give **zero evidence trail**, so their output is unusable for anything with the institution's name on it.

## 5. Target users

- **Primary:** University research/press office communication officers.
- **Secondary:** Principal Investigators & PhD students who must self-promote their work.
- **Tertiary:** Science journalists, faculty social-media managers, grant-office staff.

## 6. Target organizations

Universities, research institutes, R&D departments, tech-transfer offices, scientific publishers, and (expansion) any organization that must communicate technical documents to the public — hospitals, NGOs, municipal science/innovation offices.

## 7. Input sources

- Open-access research papers & preprints (PDF): **arXiv, DOAJ, PubMed Central, university repositories** — all legally usable.
- Optional: research reports, technical documentation, educational materials (user-supplied → licensing-clean).
- Handles: multi-column PDFs, figures, tables, references. (Scanned-doc OCR = stretch.)

## 8. AI processing pipeline (high level)

```
Paper (PDF)
  → Ingestion & structure-aware parsing (sections, figures, tables, refs)
  → Fact & claim extraction  → Claim store with source spans (page/section/quote)
  → Retrieval (RAG over the paper's own chunks)
  → Audience-adaptive generation (citation-aware, structured output)
  → TrustLayer verification: each sentence classified + grounded + confidence-scored
  → Human-review dashboard (accept / edit / flag)
  → Final bilingual outputs (HU/EN)
```

## 9. Output types

Press release · public-facing lay article · LinkedIn/X social posts · executive summary · **short video script (60s)** — each in **Hungarian and English**, each with an inline evidence trail.

## 10. Core value proposition

**Trustworthy, traceable science communication at 10× speed.** You don't just get content — you get content where every claim shows its receipts, so a press officer can approve it in minutes instead of re-reading the paper.

## 11. What makes it unique

1. **Evidence-linked claims** — every generated sentence traces back to page/section/quote.
2. **TrustLayer** — sentences are typed as *explicit fact / reasonable interpretation / rhetorical framing / unsupported*, with confidence scores; unsupported claims are blocked or flagged.
3. **Bilingual scientific rewriting** (HU↔EN), not just translation — audience-adapted per language.
4. **Human-in-the-loop review dashboard** designed for a comms officer's real workflow.
5. **Multi-audience fan-out** from one verified claim store — write the facts once, render for five audiences.

## 12. What makes it different from…

| Tool | What it does | Why UniPress beats it |
|---|---|---|
| **ChatGPT** | Fluent text, confident, **no traceability**, hallucinates | Every claim grounded + audited; blocks unsupported statements |
| **Generic PDF-chat** | Q&A over a doc | Produces *finished communication artifacts*, not answers; multi-audience, bilingual |
| **Summarization tools** | Compress text | Doesn't just shorten — *re-purposes* for distinct audiences with fact constraints |
| **Content-gen tools (Jasper etc.)** | Marketing copy from prompts | Grounded in *your source document*; verification-first, built for scientific accuracy |

---

## Pitches

### Elevator pitch (1 line)

> UniPress DE turns research papers into trustworthy, bilingual press materials where every claim is traceable to the source — approvable in minutes, not hours.

### 30-second pitch

> Every university produces research the public never hears about, because turning a dense paper into an accurate press release is slow, manual work — and generic AI tools make it riskier by hallucinating with no evidence trail. UniPress DE ingests a research paper, extracts its factual claims with exact source locations, and generates a press release, public article, social posts, and a video script — in Hungarian and English. The difference is our verification layer: every sentence is classified and grounded to the source, so unsupported claims are caught *before* a human reviews them. It's science communication you can actually trust — at ten times the speed.

### 3-minute presentation pitch (structure)

1. **Hook (20s):** "This university published 40 papers last month. How many did you hear about? The bottleneck isn't research — it's the last mile of communication."
2. **Problem (30s):** Manual, slow, error-prone; generic AI hallucinates with no traceability → unusable for institutional comms.
3. **Solution + live demo (90s):** Drop in a paper → watch it produce a bilingual press release + video script, with a claim highlighted and its source quote shown side-by-side; then show the TrustLayer flagging an overclaim it refused to make.
4. **How it works (20s):** One diagram — ingestion → claim store → RAG generation → verification → human review.
5. **Why it matters / expansion (20s):** Works for grants, education, any technical doc; locally deployable; built for the research office that's grading this competition.

---

## One-page competition description (draft — fits A4, font 12, single spacing)

> **UniPress DE — Trustworthy AI Science Communication**
>
> **The problem.** Universities produce far more research than they can communicate. Translating a technical paper into an accurate, public-facing press release is slow, manual work reserved for a few communication staff — and general-purpose AI tools make it *riskier*, generating fluent but unverifiable text that can misstate findings under the institution's name.
>
> **The solution.** UniPress DE is an AI system that transforms a research paper into a full set of communication materials — press release, public article, social-media posts, executive summary, and a short video script — in both Hungarian and English. Its core innovation is **verifiable generation**: the system first extracts the paper's factual claims and records the exact location of each (page, section, supporting quote), then generates communication content constrained to those claims. A verification layer ("TrustLayer") classifies every generated sentence as an explicit fact, a reasonable interpretation, rhetorical framing, or an unsupported claim, assigns a confidence score, and blocks or flags anything not grounded in the source. A human-review dashboard lets a communication officer accept, edit, or reject each element with the evidence shown alongside — cutting approval from hours to minutes.
>
> **Why it's credible.** Built on a hybrid architecture: open-source parsing, embeddings, retrieval, and verification for transparency and local deployability, with a swappable frontier LLM for generation quality. Evaluated on real metrics — factual accuracy, hallucination rate, source faithfulness, and reviewer satisfaction — not vibes.
>
> **Why it matters here.** The target users are university research and press offices — the very institutions running this challenge. The same engine extends to grant impact reporting, educational communication, and any domain that must turn technical documents into public language it can trust.

---

## Decisions on record

| Decision | Choice | Rationale |
|---|---|---|
| Category | 2.C — AI-Assisted PR Content Generation | Matches user's strengths + strongest competition fit |
| Concept | UniPress (newsroom) + TrustLayer core + video module | Best blend of value, demoability, technical depth, expansion |
| Build mode | Solo | Scope kept tight; ruthless MVP prioritization |
| LLM strategy | Hybrid | OSS core (retrieval/embeddings/verification) + swappable hosted LLM for generation quality; supports "locally deployable" narrative |
| Languages | Hungarian + English | Genuine differentiator in this context |

## Next phase

**System Requirements & Architecture** — justify each component (and deliberately exclude the ones not warranted for a solo MVP), with Mermaid diagrams and an MVP / competition / production split.
