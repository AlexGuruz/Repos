from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pathlib import Path
from unittest.mock import patch

from routers import repo


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(repo.router)
    return TestClient(app)


def test_repo_tree_returns_empty_when_governance_root_missing():
    with patch.object(repo.settings, "ai_lab_governance_root", ""):
        client = _client()
        response = client.get("/api/repo/tree")

    assert response.status_code == 200
    assert response.json()["tree"] == []


def test_repo_tree_walks_configured_root(tmp_path):
    root = tmp_path / "governance"
    nested = root / "docs"
    nested.mkdir(parents=True)
    (nested / "policy.md").write_text("hello", encoding="utf-8")

    with patch.object(repo.settings, "ai_lab_governance_root", str(root)):
        client = _client()
        response = client.get("/api/repo/tree")

    assert response.status_code == 200
    tree = response.json()["tree"]
    assert any(item["type"] == "file" and item["name"] == "policy.md" for item in tree)


def test_repo_file_returns_metadata(tmp_path):
    target = tmp_path / "sample.txt"
    target.write_text("hello repo", encoding="utf-8")

    client = _client()
    response = client.get("/api/repo/file", params={"path": str(target)})

    assert response.status_code == 200
    body = response.json()
    assert body["path"] == str(target)
    assert body["size_bytes"] == len("hello repo")
