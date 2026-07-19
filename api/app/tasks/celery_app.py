"""Celery application. Redis is broker + result backend.

Referenced by compose as `app.tasks.celery_app.celery` for the worker and flower.
"""

from __future__ import annotations

from celery import Celery

from app.core.settings import get_settings
from app.core.telemetry import instrument_celery, setup_tracing

settings = get_settings()

celery = Celery(
    "unipress",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.chains"],
)
celery.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Wire tracing in the worker process too, so api -> worker spans connect.
setup_tracing(settings)
instrument_celery()
