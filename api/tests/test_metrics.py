"""The app-specific Prometheus series appear on /metrics after the pipeline runs."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.test_ingestion import make_pdf

PAPER = (
    "1. Introduction\n\n"
    "The system achieved 88.8% accuracy across 339 smears. "
    "However, the approach is limited to born-digital images."
)


def test_stage_metrics_exposed_after_pipeline(client: TestClient) -> None:
    doc_id = client.post(
        "/documents", files={"file": ("p.pdf", make_pdf([PAPER]), "application/pdf")}
    ).json()["id"]
    client.post(
        f"/documents/{doc_id}/outputs", json={"output_type": "PRESS_RELEASE", "language": "en"}
    )

    metrics = client.get("/metrics").text
    # Stage latency + throughput recorded for the stages that ran inline.
    assert "unipress_stage_seconds" in metrics
    assert 'unipress_stage_total{stage="parse",status="ok"}' in metrics
    assert 'unipress_stage_total{stage="generate",status="ok"}' in metrics
    # The queue-depth collector is registered (series present even if Redis is absent).
    assert "unipress_celery_queue_depth" in metrics or "queue_depth" in metrics
