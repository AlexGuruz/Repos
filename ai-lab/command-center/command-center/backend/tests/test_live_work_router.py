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
