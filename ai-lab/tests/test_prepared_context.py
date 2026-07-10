from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
import time

from brain.orchestrator.main import run
from brain.prepared_context.builders import build_repo_pulse, build_system_snapshot
from brain.prepared_context.loader import is_snapshot_stale, try_prepared_context_answer
from brain.prepared_context.schema import validate_snapshot_dict
from brain.prepared_context.store import load_snapshot, write_snapshot


def test_snapshot_schema_validation_passes_for_builder_output():
    snap = build_system_snapshot()
    ok, errs = validate_snapshot_dict(snap.to_dict())
    assert ok is True
    assert errs == []


def test_stale_snapshot_behavior_detects_old_generated_at():
    snap = build_system_snapshot().to_dict()
    old = datetime.now(timezone.utc) - timedelta(days=2)
    snap["generated_at"] = old.strftime("%Y-%m-%dT%H:%M:%SZ")
    snap["freshness_seconds"] = 60
    assert is_snapshot_stale(snap) is True


def test_missing_snapshot_falls_back_to_none(monkeypatch):
    from brain.prepared_context import loader

    monkeypatch.setattr(loader, "load_snapshot_fresh", lambda snapshot_type: None)
    out = try_prepared_context_answer("what systems are active?", "answer")
    assert out is None


def test_orchestrator_uses_prepared_context_for_common_system_question():
    write_snapshot(build_system_snapshot())
    out = run("what systems are active?", llm_base_url="", llm_model="", session_id=f"pc_{uuid.uuid4().hex[:8]}")
    assert "system_snapshot" in out["reply"]
    assert "generated_at" in out["reply"]


def test_worker_not_called_for_prepared_context_repo_question(monkeypatch):
    import brain.worker_health as wh

    def _boom(*args, **kwargs):
        raise AssertionError("worker health should not be called for prepared-context repo questions")

    monkeypatch.setattr(wh, "get_worker_health_snapshot", _boom)
    write_snapshot(build_repo_pulse())
    out = run("summarize current repo status", llm_base_url="", llm_model="", session_id=f"pc_{uuid.uuid4().hex[:8]}")
    assert "repo_pulse" in out["reply"] or "Prepared context" in out["reply"]


def test_trace_records_prepared_context_fields():
    from brain.orchestrator.response_trace import trace_file_path

    write_snapshot(build_system_snapshot())
    rid = f"pc-trace-{uuid.uuid4().hex[:8]}"
    _ = run(
        "what systems are active?",
        llm_base_url="",
        llm_model="",
        session_id=f"pc_{uuid.uuid4().hex[:8]}",
        request_id=rid,
        write_response_trace=True,
    )
    tf = trace_file_path()
    lines = tf.read_text(encoding="utf-8", errors="replace").splitlines()
    rec = None
    for line in reversed(lines):
        row = json.loads(line)
        if row.get("request_id") == rid:
            rec = row
            break
    assert rec is not None
    assert rec.get("prepared_context_used") is True
    assert rec.get("snapshot_types_used")
    assert "context_load_ms" in rec
    assert rec.get("final_answer_source") in ("prepared_context", "prepared_context_plus_model")


def test_generated_at_and_sources_preserved():
    write_snapshot(build_repo_pulse())
    stored = load_snapshot("repo_pulse")
    assert stored is not None
    assert stored.get("generated_at")
    assert isinstance(stored.get("source_files_or_tools"), list)
    assert len(stored.get("source_files_or_tools")) >= 1


def test_repo_documentation_status_uses_prepared_context_and_is_fast(monkeypatch):
    import brain.worker_health as wh

    def _boom(*args, **kwargs):
        raise AssertionError("worker should not be called for repo documentation status")

    monkeypatch.setattr(wh, "get_worker_health_snapshot", _boom)
    write_snapshot(build_repo_pulse())
    t0 = time.perf_counter()
    out = run(
        "explain repo documentation status",
        llm_base_url="",
        llm_model="",
        session_id=f"pc_{uuid.uuid4().hex[:8]}",
    )
    elapsed = (time.perf_counter() - t0)
    assert elapsed < 1.5, f"expected fast path under 1.5s, got {elapsed:.3f}s"
    assert "documentation_cleanup_status" in out["reply"] or "repo_pulse" in out["reply"]


def test_final_answer_source_not_unknown_for_repo_documentation_status():
    from brain.orchestrator.response_trace import trace_file_path

    write_snapshot(build_repo_pulse())
    rid = f"pc-doc-{uuid.uuid4().hex[:8]}"
    _ = run(
        "explain repo documentation status",
        llm_base_url="",
        llm_model="",
        session_id=f"pc_{uuid.uuid4().hex[:8]}",
        request_id=rid,
        write_response_trace=True,
    )
    lines = trace_file_path().read_text(encoding="utf-8", errors="replace").splitlines()
    rec = None
    for line in reversed(lines):
        row = json.loads(line)
        if row.get("request_id") == rid:
            rec = row
            break
    assert rec is not None
    assert rec.get("final_answer_source") in ("prepared_context", "prepared_context_plus_model", "retrieval", "model", "orchestrator_fallback", "tool")
    assert rec.get("final_answer_source") != "unknown"


def test_quality_gate_low_quality_returns_limited_summary():
    from brain.prepared_context import loader

    weak = build_repo_pulse().to_dict()
    weak["evidence_items"] = []
    weak["confidence"] = 0.4
    weak["stale"] = True

    def _fake(snapshot_type: str):
        if snapshot_type in ("repo_pulse", "system_snapshot"):
            return weak
        return None

    original = loader.load_snapshot_fresh
    loader.load_snapshot_fresh = _fake
    try:
        out = try_prepared_context_answer("explain repo documentation status", "answer")
    finally:
        loader.load_snapshot_fresh = original
    assert out is not None
    assert out.get("prepared_quality_low") is True
    assert out.get("prepared_quality_score", 1.0) < 0.62
    assert "limited_summary" in out.get("reply", "")
    assert "missing_data" in out.get("reply", "")

