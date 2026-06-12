from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

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


def test_permanent_rule_endpoint_derives_scoped_match_from_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_LAB_PERMANENT_ALLOWLIST_PATH", str(tmp_path / "rules.json"))
    pending = {
        "action_type": "run_approved",
        "file_path": "registry/safe_report.py",
        "reason": "scheduled report",
    }
    with patch.object(events, "list_pending", return_value=[("approval-1", pending)]), \
         patch.object(events.bus, "publish") as publish:
        client = _client()
        response = client.post("/api/approvals/permanent", json={"approval_id": "approval-1"})

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["rule"]["action"] == "run_approved"
    assert body["rule"]["match"]["file_path"] == "registry/safe_report.py"
    assert publish.await_count == 1

    assert client.get("/api/approvals/permanent").json()["rules"][0]["id"] == body["rule"]["id"]


def test_permanent_rule_endpoint_rejects_forbidden_actions(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_LAB_PERMANENT_ALLOWLIST_PATH", str(tmp_path / "rules.json"))
    client = _client()

    response = client.post(
        "/api/approvals/permanent",
        json={"action": "restart_service", "match": {"target": "worker"}},
    )

    assert response.status_code == 400
    assert "cannot be permanently allowlisted" in response.json()["detail"]
