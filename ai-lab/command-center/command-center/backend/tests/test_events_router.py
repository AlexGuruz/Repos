from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from routers import events


class _ExecutionResult:
    def __init__(self, success: bool = True, stdout: str = "ok", stderr: str = "", exit_code: int = 0):
        self.success = success
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
        }


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(events.router)
    return TestClient(app)


def test_list_approvals_returns_pending_queue():
    with patch.object(events, "list_pending", return_value=[("APR-1", {"agent": "orchestrator", "action": "restart", "detail": "Needs approval", "created_at": "2026-03-16T00:00:00Z"})]):
        client = _client()
        response = client.get("/api/approvals")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == "APR-1"
    assert data[0]["status"] == "pending"


def test_resolve_approval_denied_without_execution():
    with patch.object(events, "list_pending", return_value=[("APR-1", {"agent": "orchestrator"})]), \
         patch.object(events, "_resolve_queue", return_value=True), \
         patch.object(events.bus, "publish") as publish:
        client = _client()
        response = client.post("/api/approvals/resolve", json={"id": "APR-1", "resolution": "denied"})

    assert response.status_code == 200
    assert response.json() == {"ok": True, "id": "APR-1", "resolution": "denied"}
    assert publish.await_count == 1


def test_resolve_approval_executes_attached_tool_when_approved():
    pending = {
        "agent": "orchestrator",
        "tool_name": "growflow_sales_today",
        "args": {"date": "today"},
        "created_at": "2026-03-16T00:00:00Z",
    }
    with patch.object(events, "list_pending", return_value=[("APR-2", pending)]), \
         patch.object(events, "_resolve_queue", return_value=True), \
         patch.object(events, "execution_run", return_value=_ExecutionResult()), \
         patch.object(events.bus, "publish") as publish:
        client = _client()
        response = client.post("/api/approvals/resolve", json={"id": "APR-2", "resolution": "approved"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["act_id"] == "ACT-APR-2"
    assert body["result"]["success"] is True
    assert publish.await_count == 2


def test_resolve_approval_executes_supervisor_payload_when_approved():
    pending = {
        "agent": "command-center",
        "supervisor_action": "run_approved",
        "supervisor_payload": {"script_path": "registry/foo.py"},
        "created_at": "2026-03-16T00:00:00Z",
    }
    with patch.object(events, "list_pending", return_value=[("approval-7", pending)]), \
         patch.object(events, "_resolve_queue", return_value=True), \
         patch("services.supervisor_bridge.execute_approved", new_callable=AsyncMock) as execute, \
         patch.object(events.bus, "publish") as publish:
        execute.return_value = {"ok": True, "act_id": "ACT-SUP", "apr_id": "approval-7"}
        client = _client()
        response = client.post("/api/approvals/resolve", json={"id": "approval-7", "resolution": "approved"})

    assert response.status_code == 200
    body = response.json()
    assert body == {"ok": True, "act_id": "ACT-SUP", "apr_id": "approval-7"}
    execute.assert_awaited_once_with(
        "approval-7",
        "command-center",
        "run_approved",
        {"script_path": "registry/foo.py"},
    )
    assert publish.await_count == 1


def test_resolve_approval_returns_error_for_missing_id():
    with patch.object(events, "list_pending", return_value=[]), \
         patch.object(events, "_resolve_queue", return_value=False), \
         patch.object(events.bus, "publish") as publish:
        client = _client()
        response = client.post("/api/approvals/resolve", json={"id": "APR-missing", "resolution": "approved"})

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert "not found" in response.json()["error"]
    assert publish.await_count == 0
