from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import retail


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(retail.router)
    return TestClient(app)


def test_retail_health_is_read_only_placeholder() -> None:
    r = _client().get("/api/retail/health")

    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["read_only"] is True
    assert body["status"] == "not_configured"
