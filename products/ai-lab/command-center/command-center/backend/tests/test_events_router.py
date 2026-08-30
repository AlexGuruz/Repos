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
         patch.object(events.channels.control, "publish", new_callable=AsyncMock) as publish:
        client = _client()
        response = client.post("/api/approvals/resolve", json={"id": "APR-1", "resolution": "denied"})

    assert response.status_code == 200
    assert response.json() == {"ok": True, "id": "APR-1", "resolution": "denied", "executed": False}
    assert publish.await_count == 1


def test_resolve_approval_queues_attached_tool_when_approved():
    pending = {
        "agent": "orchestrator",
        "tool_name": "growflow_sales_today",
        "args": {"date": "today"},
        "created_at": "2026-03-16T00:00:00Z",
    }
    with patch.object(events, "list_pending", return_value=[("APR-2", pending)]), \
         patch.object(events, "_resolve_queue", return_value=True), \
         patch.object(events, "_kickoff_approved_execution") as kickoff, \
         patch.object(events.channels.control, "publish", new_callable=AsyncMock) as publish:
        client = _client()
        response = client.post("/api/approvals/resolve", json={"id": "APR-2", "resolution": "approved"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["act_id"] == "ACT-APR-2"
    assert body.get("executed") is True
    assert body.get("execute_queued") is True
    kickoff.assert_called_once_with("APR-2", pending)
    assert publish.await_count == 1


def test_resolve_approval_returns_error_for_missing_id():
    with patch.object(events, "list_pending", return_value=[]), \
         patch.object(events, "_resolve_queue", return_value=False), \
         patch.object(events.channels.control, "publish", new_callable=AsyncMock) as publish:
        client = _client()
        response = client.post("/api/approvals/resolve", json={"id": "approval-missing", "resolution": "approved"})

    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert "not found" in response.json()["error"]
    assert publish.await_count == 0


def test_run_approved_execution_publishes_error_without_failing_resolve_path():
    import asyncio

    pending = {
        "agent": "orchestrator",
        "tool_name": "broken_tool",
        "args": {},
        "created_at": "2026-03-16T00:00:00Z",
    }
    with patch.object(events, "_execute_approved", side_effect=RuntimeError("boom")), \
         patch.object(events.channels.control, "publish", new_callable=AsyncMock) as publish:
        asyncio.run(events._run_approved_execution("approval-99", pending))

    assert publish.await_count >= 1
    assert publish.await_args.args[0] == "action"
    assert "execution failed" in publish.await_args.args[1]["detail"]


def test_create_permanent_rule_from_approval_id():
    pending = {
        "file_path": "operator_desk",
        "action_type": "operator_desk_tool",
        "reason": "scoped",
        "tool_name": "growflow_status",
        "args": {},
        "created_at": "2026-03-16T00:00:00Z",
    }
    with patch.object(events, "list_pending", return_value=[("approval-7", pending)]), \
         patch.object(events, "add_rule", return_value={"id": "PAR-TEST", "action": "operator_desk_tool", "match": {"tool_name": "growflow_status"}}), \
         patch.object(events.channels.control, "publish", new_callable=AsyncMock), \
         patch.object(events.channels.ops, "publish", new_callable=AsyncMock):
        client = _client()
        response = client.post("/api/approvals/permanent", json={"approval_id": "approval-7", "note": "from test"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["rule"]["id"] == "PAR-TEST"


def test_create_permanent_rule_rejects_already_resolved_approval():
    """Always Approve guardrail: permanent-before-resolve — 409 if not pending."""
    with patch.object(events, "list_pending", return_value=[]):
        client = _client()
        response = client.post(
            "/api/approvals/permanent",
            json={"approval_id": "approval-gone", "note": "too late"},
        )
    assert response.status_code == 409
    assert "already resolved" in response.json()["detail"].lower() or "missing" in response.json()["detail"].lower()
