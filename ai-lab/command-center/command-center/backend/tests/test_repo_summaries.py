"""
Tests for GET /api/repo/summaries (repo scan list for Repo panel).
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import repo


@pytest.fixture
def summaries_tmpdir(tmp_path):
    summaries_dir = tmp_path / "summaries" / "repos"
    summaries_dir.mkdir(parents=True)
    return summaries_dir


def test_repo_summaries_empty(summaries_tmpdir):
    ai_lab_root = Path(summaries_tmpdir).parent.parent  # so AI_LAB_ROOT / "summaries" / "repos" == summaries_tmpdir
    with patch.object(repo, "AI_LAB_ROOT", ai_lab_root):
        app = FastAPI()
        app.include_router(repo.router)
        client = TestClient(app)
        r = client.get("/api/repo/summaries")
    assert r.status_code == 200
    data = r.json()
    assert "summaries" in data
    assert data["summaries"] == []


def test_repo_summaries_returns_list(summaries_tmpdir):
    (summaries_tmpdir / "ai-lab.json").write_text(
        json.dumps({
            "repo": "ai-lab",
            "path": "/some/path/ai-lab",
            "entrypoints": ["main.py", "package.json"],
        }),
        encoding="utf-8",
    )
    (summaries_tmpdir / "other.json").write_text(
        json.dumps({"repo": "other", "path": "", "entrypoints": []}),
        encoding="utf-8",
    )
    ai_lab_root = summaries_tmpdir.parent.parent  # tmp_path/summaries/repos -> tmp_path
    with patch.object(repo, "AI_LAB_ROOT", ai_lab_root):
        app = FastAPI()
        app.include_router(repo.router)
        client = TestClient(app)
        r = client.get("/api/repo/summaries")
    assert r.status_code == 200
    data = r.json()
    summaries = data["summaries"]
    assert len(summaries) == 2
    names = {s["name"] for s in summaries}
    assert "ai-lab" in names
    assert "other" in names
    one = next(s for s in summaries if s["name"] == "ai-lab")
    assert one["path"] == "/some/path/ai-lab"
    assert "main.py" in one["entrypoints"]
