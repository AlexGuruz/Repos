from __future__ import annotations

import json
from pathlib import Path

import pytest

from brain.live_work_orchestration import schema
from brain.live_work_orchestration.builders import build_all_live_work_snapshots
from brain.live_work_orchestration.compiler import compile_daily_plan_preview
from brain.orchestrator.approval_gate import APPROVAL_REQUIRED, AUTO_ALLOWED, requires_approval


def test_schema_roundtrip() -> None:
    w = schema.WorkDemand(
        id="1",
        source="test",
        confidence=0.9,
        observed_at="2026-01-01T00:00:00Z",
        created_at="2026-01-01T00:00:00Z",
        notes="n",
        evidence=["e"],
        status="open",
        title="t",
        project_hint="p",
    )
    d = w.to_dict()
    w2 = schema.WorkDemand(**d)
    assert w2.to_dict() == d


def test_snapshot_builder_writes_files(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    build_all_live_work_snapshots()
    for name in (
        "work_demand_snapshot",
        "time_constraints_snapshot",
        "daily_progress_snapshot",
        "communication_queue_snapshot",
        "planning_gaps_snapshot",
        "clickup_action_snapshot",
        "index",
    ):
        p = tmp_path / f"{name}.json"
        assert p.is_file(), name


def test_snapshots_include_metadata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    build_all_live_work_snapshots()
    raw = json.loads((tmp_path / "work_demand_snapshot.json").read_text(encoding="utf-8"))
    assert raw.get("generated_at")
    assert "confidence" in raw
    assert isinstance(raw.get("evidence_items"), list)
    assert isinstance(raw.get("missing_sources"), list)


def test_daily_plan_preview_sections(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    build_all_live_work_snapshots()
    prev = compile_daily_plan_preview()
    for key in (
        "today",
        "before_shift",
        "during_shift",
        "after_shift",
        "top_priorities",
        "constraints",
        "risks_to_watch",
        "a_good_day_looks_like",
    ):
        assert key in prev and isinstance(prev[key], str)


def test_compiler_has_no_automatic_external_side_effects(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    build_all_live_work_snapshots()
    prev = compile_daily_plan_preview()
    blob = json.dumps(prev).lower()
    assert "asana_task_created" not in blob
    assert "slack_message_sent" not in blob
    assert "clickup_task_created" not in blob
    assert "read-only" in (prev.get("notes") or "").lower()


def test_local_activity_worker_is_stub() -> None:
    from brain.live_work_orchestration.workers import LocalActivityWorker

    out = LocalActivityWorker().collect()
    assert out.get("stub") is True
    assert out.get("read_only") is True


def test_missing_sources_not_guessed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    build_all_live_work_snapshots()
    cq = json.loads((tmp_path / "communication_queue_snapshot.json").read_text(encoding="utf-8"))
    assert isinstance(cq.get("missing_sources"), list)
    assert len(cq.get("missing_sources") or []) > 0


def test_approval_gates_not_weakened() -> None:
    assert "send" in APPROVAL_REQUIRED
    assert requires_approval("patch", None) is True
    assert "live_work_fake_action" not in AUTO_ALLOWED
