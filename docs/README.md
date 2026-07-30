# Documentation

Two kinds of document live here, and the distinction matters when you read them.

**[`09-live-system.md`](09-live-system.md) describes the system as it runs.** Start there to understand, use, operate or clone it. It is authoritative wherever it disagrees with anything else in this folder.

**`01`–`08` are the record of how the system was designed and built.** The series was written before the code and is kept as written, so the reasoning behind each decision — and each deviation from it — stays legible. They are history and rationale, not instructions or outstanding work.

## Current

| Doc | Read it for |
|---|---|
| [09 — The Live System](09-live-system.md) | What is deployed, the API with a worked example, how it is operated, what is measured, and where it falls short |

Plus the [project README](../README.md) for the pitch, the pipeline diagram and a local quickstart.

## Design record

| Doc | Read it for |
|---|---|
| [01 — Project Definition](01-project-definition.md) | The problem, the users, the pitch, what is in and out of scope |
| [02 — System Architecture](02-architecture.md) | Components and their boundaries; the ports that keep adapters swappable |
| [03 — AI Pipeline & Anti-Hallucination](03-ai-pipeline.md) | Data contracts, claim extraction, generation binding, the TrustLayer algorithm |
| [04 — Content Generation Spec](04-content-outputs.md) | The five output types and how one claim set fans out without losing fidelity |
| [05 — Evaluation Framework](05-evaluation.md) | Faithfulness, hallucination, coverage and readability metrics, and their targets |
| [06 — Dataset & Testing Strategy](06-dataset-strategy.md) | Corpus, licensing, the gold and adversarial sets, messy-PDF handling |
| [07 — Technology Stack](07-tech-stack.md) | Every technology choice with its justification and its alternatives |

## Build record

| Doc | Read it for |
|---|---|
| [08 — Build Record](08-dev-plan.md) | The phase sequence with an outcome log per phase: what was built, what was verified, what was deviated from or deferred |

## Reading paths

- **Evaluating the project** — [`09`](09-live-system.md), then [`03`](03-ai-pipeline.md) for how the trust guarantee works, then [`05`](05-evaluation.md) for how it is measured.
- **Running or operating it** — [`09` §7](09-live-system.md#7-operating-it) and [`09` §10](09-live-system.md#10-running-it-yourself).
- **Extending it** — [`02`](02-architecture.md) for the port boundaries, [`07`](07-tech-stack.md) for why each component was chosen, [`08`](08-dev-plan.md) for what was already tried.
- **Judging the engineering process** — [`08`](08-dev-plan.md) end to end: each phase records its deviations honestly, including the ones that cost time.
