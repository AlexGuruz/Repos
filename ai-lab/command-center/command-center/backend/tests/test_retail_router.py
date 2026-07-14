from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import retail


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(retail.router)
    return TestClient(app)


def test_retail_health_fails_closed_when_unconfigured():
    r = _client().get("/api/retail/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert body["status"] == "unavailable"


def test_retail_capital_approve_does_not_succeed_without_service():
    r = _client().post("/api/retail/capital/scenario/ap-1/approve")
    assert r.status_code == 409
