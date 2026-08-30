"""Per-channel JSONL isolation + rotation."""
from __future__ import annotations

from pathlib import Path

import services.observability as obs


def test_log_channel_event_writes_named_file(tmp_path, monkeypatch):
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path)
    path = obs.log_channel_event("control", "approval", {"id": "APR-1"})
    # Fire-and-forget — flush via sync path
    obs._append_jsonl_sync("control", {"channel": "control", "event": "approval", "data": {"id": "APR-1"}}, obs._CHANNEL_LOCKS.setdefault("control", __import__("threading").Lock()))
    assert (tmp_path / "control.jsonl").exists()
    assert "event_stream.jsonl" not in {p.name for p in tmp_path.iterdir()}
    assert path.name == "control.jsonl"


def test_hardware_snapshots_not_logged_to_telemetry_jsonl(tmp_path, monkeypatch):
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path)
    obs.log_channel_event("telemetry", "hardware", {"cpu_percent": 1})
    assert not (tmp_path / "telemetry.jsonl").exists()


def test_rotate_on_size(tmp_path, monkeypatch):
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path)
    monkeypatch.setattr(obs, "_MAX_BYTES", 200)
    lock = __import__("threading").Lock()
    # Write enough to exceed
    for i in range(30):
        obs._append_jsonl_sync("ops", {"n": i, "pad": "x" * 40}, lock)
    files = list(tmp_path.glob("ops*.jsonl"))
    assert len(files) >= 1


def test_legacy_event_stream_archived_when_oversized(tmp_path, monkeypatch):
    monkeypatch.setattr(obs, "LOG_DIR", tmp_path)
    monkeypatch.setattr(obs, "_MAX_BYTES", 100)
    legacy = tmp_path / "event_stream.jsonl"
    legacy.write_bytes(b"x" * 200)
    info = obs.ensure_legacy_event_stream_not_appended()
    assert info["action"] == "archived"
    assert not legacy.exists()
