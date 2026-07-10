from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from brain.orchestrator.main import run
from brain.orchestrator.approval_gate import requires_approval
from brain.prepared_context.builders import build_repo_pulse
from brain.prepared_context.store import write_snapshot
from brain.repo_docs_maintainer import (
    analyze_repo_docs_status,
    build_docs_cleanup_plan,
    create_docs_update_proposal,
)


def test_status_uses_repo_pulse_prepared_context() -> None:
    write_snapshot(build_repo_pulse())
    status = analyze_repo_docs_status(message="what docs need cleanup?")
    assert status["ok"] is True
    assert status.get("generated_at")
    assert "stale" in status
    assert isinstance(status.get("source_paths"), list)


def test_cleanup_plan_returns_prioritized_items() -> None:
    write_snapshot(build_repo_pulse())
    plan = build_docs_cleanup_plan(message="make a docs cleanup plan")
    assert plan["ok"] is True
    assert "plan_items" in plan
    if plan["plan_items"]:
        first = plan["plan_items"][0]
        for k in (
            "repo",
            "doc_file",
            "issue_found",
            "recommended_update",
            "risk_level",
            "approval_required",
            "suggested_verification",
            "readme_validation",
            "priority_score",
        ):
            assert k in first


def test_update_proposal_requires_approval_and_no_direct_write() -> None:
    write_snapshot(build_repo_pulse())
    prop = create_docs_update_proposal(message="prepare a docs update proposal")
    assert prop.get("approval_required") is True
    assert prop.get("no_direct_write_performed") is True
    assert prop.get("action_classification") == "modifies-files-or-state"
    assert requires_approval("write_docs_update", "write_docs_update") is True


def test_docs_status_and_plan_do_not_call_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    import brain.worker_health as wh

    def _boom(*args, **kwargs):
        raise AssertionError("worker must not be called for docs status/plan")

    monkeypatch.setattr(wh, "get_worker_health_snapshot", _boom)
    write_snapshot(build_repo_pulse())
    out1 = run("what docs need cleanup?", llm_base_url="", llm_model="", session_id=f"docs-{uuid.uuid4().hex[:6]}")
    out2 = run("make a docs cleanup plan", llm_base_url="", llm_model="", session_id=f"docs-{uuid.uuid4().hex[:6]}")
    assert "repo_documentation_status" in out1["reply"]
    assert "docs_cleanup_plan" in out2["reply"]


def test_missing_repo_pulse_returns_limited_plan(monkeypatch: pytest.MonkeyPatch) -> None:
    from brain import repo_docs_maintainer as rdm

    monkeypatch.setattr(rdm, "load_snapshot_fresh", lambda snapshot_type: None)
    plan = build_docs_cleanup_plan(message="plan documentation updates")
    assert plan["limited"] is True
    assert "missing_repo_pulse_snapshot" in (plan.get("missing_data") or [])


def test_docs_update_proposal_enqueues_approval(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write_snapshot(build_repo_pulse())
    sentinel = Path(__file__).resolve().parents[1] / "docs" / "AI_ROUTING_POLICY.md"
    before = sentinel.read_text(encoding="utf-8")
    out = run(
        "prepare a docs update proposal",
        llm_base_url="",
        llm_model="",
        session_id=f"docs-prop-{uuid.uuid4().hex[:6]}",
    )
    assert "docs_update_proposal" in out["reply"]
    assert out.get("approval_request") is not None
    after = sentinel.read_text(encoding="utf-8")
    assert after == before, "proposal flow must not directly edit docs files"

