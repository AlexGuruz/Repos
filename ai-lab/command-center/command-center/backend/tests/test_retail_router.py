from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import retail


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(retail.router)
    return TestClient(app)


def test_retail_health_is_disabled_safe() -> None:
    response = _client().get("/api/retail/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "disabled"
    assert body["available"] is False


def test_retail_mutating_actions_fail_closed() -> None:
    response = _client().post("/api/retail/refresh", json={})

    assert response.status_code == 503
    assert "backend not configured" in response.json()["detail"]
