"""Expose the worker's Prometheus metrics over HTTP for Prometheus to scrape.

Celery runs tasks in prefork child processes, so the stage/LLM metrics are recorded
across several processes. Prometheus' multiprocess mode (PROMETHEUS_MULTIPROC_DIR)
has each process write to a shared dir; the main worker process then serves the
aggregated registry on WORKER_METRICS_PORT. All best-effort — a failure here must
never stop the worker from processing tasks.

Requires PROMETHEUS_MULTIPROC_DIR to be set in the environment *before* the metric
families are created (compose sets it on the worker service). Without it, this is a
no-op and the worker simply exposes no metrics endpoint.
"""

from __future__ import annotations

import os

from celery.signals import celeryd_init, worker_process_shutdown

from app.core.logging import get_logger

log = get_logger("worker.metrics")


@celeryd_init.connect
def start_worker_metrics_server(**_: object) -> None:
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if not multiproc_dir:
        return
    try:
        os.makedirs(multiproc_dir, exist_ok=True)
        from prometheus_client import CollectorRegistry, multiprocess, start_http_server

        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        port = int(os.environ.get("WORKER_METRICS_PORT", "9100"))
        start_http_server(port, registry=registry)
        log.info("worker.metrics_server_started", port=port)
    except Exception as exc:  # pragma: no cover - infra path
        log.warning("worker.metrics_server_failed", error=str(exc))


@worker_process_shutdown.connect
def _cleanup_worker_metrics(pid: int | None = None, **_: object) -> None:
    """Flush a child's multiprocess metric files on exit (prometheus_client contract)."""
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR")
    if not multiproc_dir or pid is None:
        return
    try:
        from prometheus_client import multiprocess

        multiprocess.mark_process_dead(pid)
    except Exception:  # pragma: no cover - infra path
        pass
