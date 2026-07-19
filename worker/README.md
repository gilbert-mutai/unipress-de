# worker/

The Celery worker currently **shares the `api/` image** — the `worker` and `flower`
services in `docker-compose.yml` build from `./api` and only change the start command.
There is no separate build here yet.

**Why:** in Phase 0 the worker loads no ML models, so a second image would be pure
duplication. Once embeddings (BGE-M3), the reranker, and NLI (DeBERTa) land in the
retrieval/trust phases, the worker graduates to its own ML-heavy image in this
directory (CUDA/torch base, model cache), while the api image stays thin.

See [`docs/07-tech-stack.md`](../docs/07-tech-stack.md) §5 and
[`docs/08-dev-plan.md`](../docs/08-dev-plan.md) Phase 0.
