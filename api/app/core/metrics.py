"""Prometheus metrics — the app-specific series behind the Grafana board (docs/05 §7, docs/07 §2.8).

Registered on the default registry, so they appear on the api's `/metrics` (via the
instrumentator) and on the worker's own metrics server. Four families back the
dashboard: per-stage latency, LLM token/cost accounting, Celery queue depth, and the
live eval metrics (hallucination / faithfulness / coverage) pushed by `eval/run_eval.py`.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from typing import Any, TypeVar

from prometheus_client import Counter, Gauge, Histogram

# Pipeline-stage latency + throughput. `stage` ∈ {parse, chunk, extract, embed, generate}.
STAGE_SECONDS = Histogram(
    "unipress_stage_seconds",
    "Pipeline stage duration in seconds",
    ["stage"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
)
STAGE_TOTAL = Counter("unipress_stage_total", "Pipeline stage runs", ["stage", "status"])

# LLM accounting (the hybrid-cost argument, docs/05 §3.5). Populated only when an LLM
# path is enabled — the default deterministic pipeline makes no calls, so these stay 0.
LLM_TOKENS = Counter("unipress_llm_tokens_total", "LLM tokens", ["model", "kind"])
LLM_COST_USD = Counter("unipress_llm_cost_usd_total", "Estimated LLM cost (USD)", ["model"])

# Live eval series (pushed by eval/run_eval.py --push-metrics).
EVAL_METRIC = Gauge("unipress_eval_metric", "Latest evaluation metric", ["metric"])

F = TypeVar("F", bound=Callable[..., Any])


@contextmanager
def stage_timer(stage: str) -> Iterator[None]:
    """Time a pipeline stage and record its latency + terminal status."""
    start = time.perf_counter()
    status = "ok"
    try:
        yield
    except Exception:
        status = "error"
        raise
    finally:
        STAGE_SECONDS.labels(stage=stage).observe(time.perf_counter() - start)
        STAGE_TOTAL.labels(stage=stage, status=status).inc()


def timed_stage(stage: str) -> Callable[[F], F]:
    """Decorator form of ``stage_timer`` for the pipeline stage functions."""

    def deco(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            with stage_timer(stage):
                return fn(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return deco


def record_llm_usage(model: str, response: Any) -> None:
    """Best-effort token + cost accounting from a LiteLLM response (never raises)."""
    try:
        usage = getattr(response, "usage", None)
        if usage is not None:
            prompt = getattr(usage, "prompt_tokens", 0) or 0
            completion = getattr(usage, "completion_tokens", 0) or 0
            LLM_TOKENS.labels(model=model, kind="prompt").inc(prompt)
            LLM_TOKENS.labels(model=model, kind="completion").inc(completion)
        import litellm

        cost = litellm.completion_cost(completion_response=response)
        if cost:
            LLM_COST_USD.labels(model=model).inc(float(cost))
    except Exception:  # metrics must never break a request
        pass


def set_eval_metrics(aggregate: dict[str, Any]) -> None:
    """Mirror an eval run's aggregate numbers onto the live gauges."""
    for name, value in aggregate.items():
        if isinstance(value, (int, float)):
            EVAL_METRIC.labels(metric=name).set(float(value))


def push_metrics(gateway_url: str, job: str = "unipress_eval") -> None:
    """Push the default registry to a Prometheus Pushgateway (for batch jobs like eval)."""
    from prometheus_client import REGISTRY, push_to_gateway

    push_to_gateway(gateway_url, job=job, registry=REGISTRY)


class QueueDepthCollector:
    """Per-scrape collector for Celery queue depth (pending tasks).

    Celery-on-Redis stores pending tasks as a list keyed by queue name; LLEN is its
    depth. Computed live on each scrape and best-effort — a scrape still succeeds if
    Redis is unreachable (the series is simply absent that scrape).
    """

    def __init__(self, queues: tuple[str, ...] = ("celery",)) -> None:
        self._queues = queues

    def collect(self) -> Iterator[Any]:
        from prometheus_client.core import GaugeMetricFamily

        family = GaugeMetricFamily(
            "unipress_celery_queue_depth", "Pending tasks per Celery queue", labels=["queue"]
        )
        try:
            import redis

            from app.core.settings import get_settings

            client = redis.Redis.from_url(get_settings().redis_url)
            for queue in self._queues:
                family.add_metric([queue], float(client.llen(queue)))
        except Exception:
            pass
        yield family


_queue_collector_registered = False


def register_queue_collector() -> None:
    """Register the queue-depth collector once (call at api startup)."""
    global _queue_collector_registered
    if _queue_collector_registered:
        return
    from prometheus_client import REGISTRY

    REGISTRY.register(QueueDepthCollector())
    _queue_collector_registered = True
