from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from routers import tools


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(tools.router)
    return TestClient(app)


def test_tools_invoke_rejects_direct_repo_index_promotion():
    with patch.object(tools, "route_intent") as route_intent:
        client = _client()
        response = client.post(
            "/api/tools/invoke",
            json={
                "op": "promote_repo_index",
                "agent": "repo_index_coordinator",
                "payload": {"repo_id": "ai-lab", "staging_version": "bad"},
            },
        )

    assert response.status_code == 403
    assert "restricted" in response.json()["detail"]
    route_intent.assert_not_called()
