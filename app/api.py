"""API FastAPI de réception des métriques."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, CollectorRegistry, generate_latest
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="System Metrics API",
    description="API de réception des métriques envoyées par les agents.",
    version="1.0.0",
)

received_metrics: list[dict[str, Any]] = []


class MetricsPayload(BaseModel):
    """Payload reçu depuis l'agent."""

    agent: str = Field(..., min_length=1)
    event_type: str
    data: dict[str, Any]


@app.get("/metrics")
def get_metrics() -> dict[str, Any]:
    """Retourne toutes les métriques reçues."""
    return {
        "total": len(received_metrics),
        "metrics": received_metrics,
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Vérifie l'état de l'API."""
    return {"status": "ok"}


@app.post("/metrics", status_code=status.HTTP_201_CREATED)
def receive_metrics(payload: MetricsPayload) -> dict[str, Any]:
    """Reçoit et stocke temporairement les métriques."""
    item = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        **payload.model_dump(),
    }
    received_metrics.append(item)

    logger.info(
        "Métriques reçues de %s. Total=%s",
        payload.agent,
        len(received_metrics),
    )

    return {
        "status": "received",
        "message": "Métriques enregistrées avec succès.",
        "total_received": len(received_metrics),
    }


@app.get("/metrics/latest")
def latest_metrics() -> dict[str, Any]:
    """Retourne la dernière métrique reçue."""
    if not received_metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune métrique disponible.",
        )

    return received_metrics[-1]


GAUGES = (
    ("system_cpu_percent", "CPU usage in percent.", "cpu", "percent"),
    ("system_memory_percent", "Memory usage in percent.", "memory", "percent"),
    ("system_memory_used_bytes", "Memory used in bytes.", "memory", "used_bytes"),
    ("system_memory_total_bytes", "Total memory in bytes.", "memory", "total_bytes"),
    ("system_memory_available_bytes", "Available memory.", "memory", "available_bytes"),
    ("system_load_1m", "1-minute load average.", "system", "load_1m"),
    ("system_load_5m", "5-minute load average.", "system", "load_5m"),
    ("system_load_15m", "15-minute load average.", "system", "load_15m"),
)


def _number(value: Any) -> float | None:
    """Retourne la valeur si elle est numerique, sinon None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


class LatestMetricsCollector:
    """Expose la derniere metrique recue au format Prometheus."""

    def collect(self):
        yield CounterMetricFamily(
            "agent_metrics_received",
            "Number of payloads received from agents.",
            value=float(len(received_metrics)),
        )
        if not received_metrics:
            return

        data = received_metrics[-1].get("data", {})
        host = str(data.get("hostname", "unknown"))
        for name, doc, group, key in GAUGES:
            section = data.get(group)
            if not isinstance(section, dict):
                continue
            value = _number(section.get(key))
            if value is None:
                continue
            family = GaugeMetricFamily(name, doc, labels=["hostname"])
            family.add_metric([host], value)
            yield family


registry = CollectorRegistry()
registry.register(LatestMetricsCollector())


@app.get("/prometheus")
def prometheus_metrics() -> Response:
    """Expose les metriques au format Prometheus."""
    return Response(
        content=generate_latest(registry),
        media_type=CONTENT_TYPE_LATEST,
    )
