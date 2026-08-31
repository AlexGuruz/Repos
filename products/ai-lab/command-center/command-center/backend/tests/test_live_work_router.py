from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from routers import live_work


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(live_work.router)
    return TestClient(app)


def test_live_work_status_ok(tmp_path: Path, monkeypatch):
    idx = tmp_path / "index.json"
    idx.write_text(json.dumps({"generated_at": "t", "snapshots": []}), encoding="utf-8")
    monkeypatch.setattr(live_work, "_live_work_dir", lambda: tmp_path)
    r = _client().get("/api/live-work/status")
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_live_work_plan_preview_calls_compiler(monkeypatch):
    fake = {"ok": True, "preview": {"today": "x", "before_shift": "b"}}
    with patch("routers.live_work._plan_preview_sync", return_value=fake):
        r = _client().get("/api/live-work/plan-preview")
    assert r.status_code == 200
    assert r.json()["preview"]["today"] == "x"


def test_live_work_clickup_queue_endpoint(monkeypatch):
    fake = {"ok": True, "items": [{"id": "cu-1"}]}
    with patch("routers.live_work._clickup_queue_sync", return_value=fake):
        r = _client().get("/api/live-work/clickup-queue")
    assert r.status_code == 200
    assert r.json()["items"][0]["id"] == "cu-1"


def test_live_work_clickup_preview_endpoint(monkeypatch):
    fake = {"ok": True, "preview": {"status": "pending approval"}}
    with patch("routers.live_work._clickup_preview_sync", return_value=fake):
        r = _client().get("/api/live-work/clickup-preview")
    assert r.status_code == 200
    assert r.json()["preview"]["status"] == "pending approval"


def test_live_work_repo_activity_ingestion_endpoint(monkeypatch):
    fake = {"ok": True, "snapshot_type": "repo_activity_snapshot", "data": {"summary": {"repos_scanned": 1}}}
    with patch("routers.live_work._repo_activity_ingestion_sync", return_value=fake):
        r = _client().get("/api/live-work/ingestion/repo-activity")
    assert r.status_code == 200
    assert r.json()["snapshot_type"] == "repo_activity_snapshot"


def test_live_work_github_activity_ingestion_endpoint(monkeypatch):
    fake = {"ok": True, "snapshot_type": "github_activity_snapshot", "data": {"correlation_summary": {}}}
    with patch("routers.live_work._github_activity_ingestion_sync", return_value=fake):
        r = _client().get("/api/live-work/ingestion/github-activity")
    assert r.status_code == 200
    assert r.json()["snapshot_type"] == "github_activity_snapshot"
