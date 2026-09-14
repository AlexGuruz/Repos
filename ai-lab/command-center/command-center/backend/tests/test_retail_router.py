from __future__ import annotations

from fastapi.testclient import TestClient


def test_backend_imports_with_retail_router():
    import main

    routes = {getattr(route, "path", "") for route in main.app.routes}
    assert "/api/retail/health" in routes


def test_retail_health_reports_unavailable_read_only_placeholder():
    import main

    client = TestClient(main.app)
    resp = client.get("/api/retail/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["kind"] == "health"
    assert body["status"] == "unavailable"
    assert "not configured" in body["reason"]
