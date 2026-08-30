from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import retail


def test_retail_health_disabled_on_acheron():
    app = FastAPI()
    app.include_router(retail.router)
    client = TestClient(app)
    r = client.get("/api/retail/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("disabled") is True
    assert body.get("available") is False
    assert "power-1" in body.get("reason", "")
