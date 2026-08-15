from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import retail


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(retail.router)
    return TestClient(app)


def test_retail_router_exposes_unavailable_status_without_startup_failure():
    response = _client().get("/api/retail/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["status"] == "unavailable"
    assert body["kind"] == "health"
