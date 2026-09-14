from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import retail


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(retail.router)
    return TestClient(app)


def test_retail_placeholder_endpoints_are_available():
    client = _client()

    health = client.get("/api/retail/health")
    dashboard = client.get("/api/retail/dashboard")
    capital = client.get("/api/retail/capital")

    assert health.status_code == 200
    assert health.json()["status"] == "unavailable"
    assert dashboard.status_code == 200
    assert dashboard.json()["rows"] == []
    assert capital.status_code == 200
    assert capital.json()["scenarios"] == []
