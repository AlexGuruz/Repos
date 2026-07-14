from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from routers import tools


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(tools.router)
    return TestClient(app)


def test_supervisor_controlled_op_queues_approval() -> None:
    with patch("services.supervisor_bridge.bus.publish", new_callable=AsyncMock):
        client = _client()
        resp = client.post("/api/tools/invoke", json={"op": "restart_service", "agent": "test", "payload": {"detail": "restart"}})
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("ok") is True
    assert body.get("queued") is True


def test_supervisor_read_only_op_still_allowed() -> None:
    with patch("services.supervisor_bridge._worker_call", new_callable=AsyncMock, return_value={"ok": True}), \
         patch("services.supervisor_bridge.bus.publish", new_callable=AsyncMock), \
         patch("services.supervisor_bridge._log_action", new_callable=AsyncMock):
        client = _client()
        resp = client.post("/api/tools/invoke", json={"op": "health", "agent": "test", "payload": {}})
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("ok") is True
    assert "result" in body


def test_supervisor_blocks_read_op_extension_without_metadata() -> None:
    with patch("services.supervisor_bridge.settings.worker_read_ops_extra", "mystery_read"), \
         patch("services.supervisor_bridge.bus.publish", new_callable=AsyncMock):
        client = _client()
        resp = client.post("/api/tools/invoke", json={"op": "mystery_read", "agent": "test", "payload": {}})
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("ok") is False
    assert "missing tool metadata" in body.get("error", "")


def test_supervisor_blocks_public_repo_index_mutations() -> None:
    with patch("services.supervisor_bridge._worker_call", new_callable=AsyncMock) as worker_call, \
         patch("services.supervisor_bridge.bus.publish", new_callable=AsyncMock):
        client = _client()
        resp = client.post("/api/tools/invoke", json={"op": "promote_repo_index", "agent": "test", "payload": {}})

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("ok") is False
    worker_call.assert_not_awaited()

