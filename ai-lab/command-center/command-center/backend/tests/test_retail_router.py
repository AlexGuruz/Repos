from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import retail


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(retail.router)
    return TestClient(app)


def test_retail_health_endpoint():
    response = _client().get("/api/retail/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["mode"] == "read_only_empty_state"


def test_retail_dashboard_empty_state():
    response = _client().get("/api/retail/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["stores"] == []


def test_retail_capital_scenario_is_preview_only():
    response = _client().post("/api/retail/capital/scenario", json={"pool": 100})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["status"] == "preview_only"
    assert body["approval_id"].startswith("retail-capital-")
