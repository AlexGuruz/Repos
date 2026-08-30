from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import repo_docs


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(repo_docs.router)
    return TestClient(app)


def test_repo_docs_status_returns_summary():
    fake = {
        "ok": True,
        "generated_at": "2026-01-01T00:00:00Z",
        "stale": False,
        "confidence": 0.9,
        "findings_count": 2,
        "readme_validations_count": 3,
        "limited": False,
        "missing_data": [],
    }
    with patch("routers.repo_docs._repo_docs_status_sync", return_value=fake):
        r = _client().get("/api/repo-docs/status")
    assert r.status_code == 200
    assert r.json()["findings_count"] == 2


def test_repo_docs_score_returns_assessment_keys():
    sample = {
        "ok": True,
        "repo_id": "ai-lab",
        "repo_path": "/mnt/workshop/Repos/products/ai-lab",
        "score_0_to_100": 72,
        "grade": "C",
        "risk_level": "medium",
    }
    with patch("routers.repo_docs._repo_docs_score_sync", return_value=sample):
        r = _client().get("/api/repo-docs/score", params={"repo": "ai-lab"})
    assert r.status_code == 200
    j = r.json()
    assert j["grade"] == "C"
    assert j["score_0_to_100"] == 72
