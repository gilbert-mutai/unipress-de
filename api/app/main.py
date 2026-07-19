"""FastAPI application entrypoint (thin: validate -> enqueue -> read)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import documents, health, jobs
from app.core.logging import configure_logging, get_logger
from app.core.settings import get_settings
from app.core.telemetry import setup_tracing

settings = get_settings()
configure_logging(settings.log_level)
setup_tracing(settings)
log = get_logger("api")

app = FastAPI(title="UniPress DE API", version="0.1.0")

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Prometheus /metrics.
Instrumentator().instrument(app).expose(app, include_in_schema=False)

# OTel FastAPI instrumentation (traces requests; connects to worker spans).
try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)
except Exception as exc:  # noqa: BLE001 - never let telemetry break boot
    log.warning("otel.fastapi.instrument_failed", error=str(exc))

app.include_router(health.router)
app.include_router(jobs.router)
app.include_router(documents.router)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"service": "unipress-de", "version": app.version, "docs": "/docs"}


log.info("api.startup", env=settings.app_env, otel=settings.otel_enabled)
