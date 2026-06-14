from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from routers import tools


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(tools.router)
    return TestClient(app)


def test_tools_invoke_blocks_coordinator_only_index_ops():
    with patch.object(tools, "route_intent") as route_intent:
        response = _client().post(
            "/api/tools/invoke",
            json={
                "op": "promote_repo_index",
                "agent": "repo_index_coordinator",
                "payload": {"repo_id": "ai-lab", "staging_version": "bad"},
            },
        )

    assert response.status_code == 403
    assert "restricted to the repo index coordinator" in response.json()["detail"]
    route_intent.assert_not_called()


def test_tools_invoke_allows_public_read_ops():
    with patch.object(tools, "route_intent", return_value={"ok": True, "result": {"matches": []}}) as route_intent:
        response = _client().post(
            "/api/tools/invoke",
            json={"op": "semantic_search", "agent": "command-center", "payload": {"query": "repo watcher"}},
        )

    assert response.status_code == 200
    assert response.json()["ok"] is True
    route_intent.assert_awaited_once_with("command-center", "semantic_search", {"query": "repo watcher"})
