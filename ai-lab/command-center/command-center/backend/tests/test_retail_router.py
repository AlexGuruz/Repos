from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import retail


def test_retail_router_imports_and_reports_unavailable():
    app = FastAPI()
    app.include_router(retail.router)

    response = TestClient(app).get("/api/retail/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["kind"] == "health"
    assert payload["status"] == "unavailable"


def test_retail_projection_placeholder_reports_unavailable():
    app = FastAPI()
    app.include_router(retail.router)

    response = TestClient(app).get("/api/retail/projection")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert payload["kind"] == "projection"
    assert payload["projection"] is None
