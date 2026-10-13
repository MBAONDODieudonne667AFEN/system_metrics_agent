import pytest
from fastapi.testclient import TestClient

from app import api

client = TestClient(api.app)


@pytest.fixture(autouse=True)
def reset_metrics():
    api.received_metrics.clear()
    yield
    api.received_metrics.clear()


def test_prometheus_endpoint_without_data():
    response = client.get("/prometheus")

    assert response.status_code == 200
    assert "agent_metrics_received_total 0.0" in response.text
    assert "system_cpu_percent" not in response.text


def test_prometheus_endpoint_with_data():
    payload = {
        "agent": "test",
        "event_type": "system_metrics",
        "data": {
            "hostname": "test-host",
            "cpu": {"percent": 12.5},
            "memory": {"percent": 40.0, "used_bytes": 1000},
            "system": {"load_1m": None},
        },
    }
    assert client.post("/metrics", json=payload).status_code == 201

    body = client.get("/prometheus").text

    assert "agent_metrics_received_total 1.0" in body
    assert 'system_cpu_percent{hostname="test-host"} 12.5' in body
    assert 'system_memory_percent{hostname="test-host"} 40.0' in body
    assert "system_load_1m" not in body
