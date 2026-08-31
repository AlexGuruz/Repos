from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from routers import chat


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(chat.router)
    return TestClient(app)


def test_chat_returns_orchestrator_reply():
    with patch.object(chat, "orchestrator_run", return_value={"reply": "hello from orchestrator", "approval_request": None}), \
         patch.object(chat.bus, "publish") as publish:
        client = _client()
        response = client.post("/api/chat", json={"message": "hello", "history": []})

    assert response.status_code == 200
    assert response.json()["text"] == "hello from orchestrator"
    assert publish.await_count == 2


def test_chat_publishes_approval_when_present():
    approval_request = {
        "id": "APR-123456",
        "agent": "orchestrator",
        "action_type": "restart_service",
        "reason": "Needs approval",
        "created_at": "2026-03-16T00:00:00Z",
    }
    with patch.object(chat, "orchestrator_run", return_value={"reply": "pending approval", "approval_request": approval_request}), \
         patch.object(chat.bus, "publish") as publish:
        client = _client()
        response = client.post("/api/chat", json={"message": "restart service", "history": []})

    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "pending approval"
    assert body["apr_id"] == "APR-123456"
    assert publish.await_count == 3


def test_chat_returns_orchestrator_error_text():
    with patch.object(chat, "orchestrator_run", side_effect=RuntimeError("boom")), \
         patch.object(chat.bus, "publish") as publish:
        client = _client()
        response = client.post("/api/chat", json={"message": "hello", "history": []})

    assert response.status_code == 200
    assert "Orchestrator error: boom" in response.json()["text"]
    assert publish.await_count == 1
