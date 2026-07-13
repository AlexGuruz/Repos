from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import retail


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(retail.router)
    return TestClient(app)


def test_retail_health_reports_not_configured() -> None:
    r = _client().get("/api/retail/health")

    assert r.status_code == 200
    assert r.json()["status"] == "not_configured"


def test_retail_import_surface_exists() -> None:
    assert retail.router.routes
