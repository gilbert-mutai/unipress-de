"""OpenTelemetry tracing setup.

Export is enabled only when OTEL_EXPORTER_OTLP_ENDPOINT is set (i.e. the
`observability` profile is running); otherwise tracing is a safe no-op, so the
`core` profile runs cleanly without a collector.
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app.core.settings import Settings

_configured = False


def setup_tracing(settings: Settings) -> None:
    """Idempotently install a TracerProvider. OTLP export is conditional."""
    global _configured
    if _configured:
        return
    _configured = True

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)

    if settings.otel_enabled:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)


def instrument_celery() -> None:
    from opentelemetry.instrumentation.celery import CeleryInstrumentor

    CeleryInstrumentor().instrument()
