from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from core.request_log import RequestIdMiddleware


def test_request_id_header_echo_and_generate():
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)

    @app.get("/api/ping")
    def ping():
        return {"ok": True}

    client = TestClient(app)
    r = client.get("/api/ping", headers={"X-Request-ID": "test-rid-1"})
    assert r.status_code == 200
    assert r.headers.get("x-request-id") == "test-rid-1"

    r2 = client.get("/api/ping")
    assert r2.headers.get("x-request-id")
    assert len(r2.headers.get("x-request-id", "")) >= 8
