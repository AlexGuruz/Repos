from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from brain.live_work_orchestration.builders import build_all_live_work_snapshots
from brain.live_work_orchestration.clickup_actions import (
    build_clickup_clarification_proposal,
    build_clickup_task_proposal,
    generate_clickup_action_recommendations,
)
from brain.live_work_orchestration.clickup_queue import (
    get_active_clarification,
    list_clarification_items,
    promote_next_clarification,
    queue_clarification,
    queue_clickup_action,
    resolve_clarification,
)
from brain.live_work_orchestration.clickup_routing import (
    classify_work_category,
    map_category_to_clickup_list,
    route_comment,
    route_task,
)
from brain.live_work_orchestration.compiler import compile_daily_plan_preview, generate_clickup_action_recommendations as compiler_generate


def test_routing_maps_exact_clickup_lists() -> None:
    assert map_category_to_clickup_list("dev_core_work") == "Dev / Core Work"
    assert map_category_to_clickup_list("agent_clarifications") == "Agent Clarifications"
    assert map_category_to_clickup_list("agent_bills") == "Agent Bills"
    assert map_category_to_clickup_list("agent_ops") == "Agent Ops"
    assert map_category_to_clickup_list("agent_system_feedback") == "Agent System Feedback"
    assert map_category_to_clickup_list("company_finances") == "Company Finances"
    assert map_category_to_clickup_list("nugz_bills") == "Nugz Bills"
    assert map_category_to_clickup_list("nugz_orders") == "Nugz Orders"


def test_route_task_and_comment_deterministic() -> None:
    assert route_task("Nugz order follow-up")["target_list"] == "Nugz Orders"
    assert route_comment("Can we confirm the bill amount?")["target_list"] == "Agent Bills"


def test_route_task_prefers_list_id_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "brain.live_work_orchestration.clickup_routing._CLICKUP_MAPPING",
        {
            "Dev / Core Work": {"list_name": "Dev / Core Work", "list_id": "cu-list-dev-123"},
        },
    )
    routed = route_task("repo feature refactor")
    assert routed["target_list"] == "cu-list-dev-123"
    assert routed["target_list_name"] == "Dev / Core Work"


def test_clarification_queue_one_active(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    a = queue_clarification(message="Q1", reason="r1")
    b = queue_clarification(message="Q2", reason="r2")
    cur = get_active_clarification()
    assert cur is not None and cur["id"] == a["id"]
    pend = [x for x in list_clarification_items() if x.get("status") in ("queued", "active")]
    assert len(pend) == 2
    q2 = next(x for x in pend if x["id"] == b["id"])
    assert q2["status"] == "queued"


def test_resolve_promotes_next(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    a = queue_clarification(message="Q1", reason="r1")
    b = queue_clarification(message="Q2", reason="r2")
    resolve_clarification(a["id"])
    cur = get_active_clarification()
    assert cur is not None and cur["id"] == b["id"]


def test_promote_next_clarification_idempotent(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    queue_clarification(message="Q1", reason="r1")
    cur1 = get_active_clarification()
    promote_next_clarification()
    cur2 = get_active_clarification()
    assert cur1 and cur2 and cur1["id"] == cur2["id"]


def test_proposals_structure_and_approval(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    wd = {"title": "Pay monthly bill", "notes": "bill due", "source": "test", "evidence": ["x"]}
    prop = build_clickup_task_proposal(wd, clickup_tool_available=False, enqueue=True)
    assert prop["target_list"] == "Agent Bills"
    assert prop["status"] == "preview-only"
    assert "preview-only" in str(prop.get("preview_reason") or "").lower()
    assert prop["action_classification"] == "external-side-effect"
    assert prop.get("approval_required") is True


def test_clarification_proposal_targets_agent_clarifications(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    prop = build_clickup_clarification_proposal(
        {"message": "Need clarification on bill due date", "reason": "missing_due_date"},
        enqueue=True,
        use_one_question_queue=True,
    )
    assert prop["target_list"] == "Agent Clarifications"
    assert prop.get("approval_required") is True
    assert prop["action_classification"] == "external-side-effect"
    assert prop.get("one_question_queue_position", 0) >= 1


def test_no_direct_execution_without_enqueue(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    a = build_clickup_task_proposal({"title": "core repo task", "notes": "feature"}, clickup_tool_available=True, enqueue=False)
    s = build_clickup_clarification_proposal({"message": "Clarify PR priority"}, enqueue=False)
    assert a.get("queue_item_id") is None
    assert s.get("clarification_queue_id") is None


def test_schema_phase9_fields_roundtrip() -> None:
    from brain.live_work_orchestration import schema

    pt = schema.PlannedTask(
        id="1",
        source="s",
        confidence=0.9,
        observed_at="t",
        created_at="t",
        notes="n",
        title="x",
        clickup_list="Dev / Core Work",
        category="dev_core_work",
        action_state="preview",
    )
    d = pt.to_dict()
    assert d["clickup_list"] == "Dev / Core Work"
    assert schema.PlannedTask(**d).to_dict() == d

    pe = schema.ProgressEvent(
        id="1",
        source="s",
        confidence=0.9,
        observed_at="t",
        created_at="t",
        notes="n",
        source_type="clickup",
    )
    d2 = pe.to_dict()
    assert d2["source_type"] == "clickup"

    cqi = schema.CommunicationQueueItem(
        id="1",
        source="s",
        confidence=0.9,
        observed_at="t",
        created_at="t",
        notes="n",
        clickup_list="Agent Clarifications",
        comm_type="followup",
    )
    out = cqi.to_dict()
    assert out["type"] == "followup"
    assert out["clickup_list"] == "Agent Clarifications"


def test_compiler_includes_clickup_recommendations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    build_all_live_work_snapshots()
    out = compile_daily_plan_preview(include_action_recommendations=True)
    rec = out.get("clickup_action_recommendations") or {}
    assert rec.get("status") == "pending approval"
    assert "plan" in rec and "clickup_actions" in rec
    assert isinstance(out.get("proposed_clickup_actions"), list)
    assert isinstance(out.get("pending_clarifications"), list)


def test_compiler_wrapper_matches_clickup_actions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    build_all_live_work_snapshots()
    base = compile_daily_plan_preview(include_action_recommendations=False)
    from brain.live_work_orchestration.builders import live_work_dir

    wd = json.loads((live_work_dir() / "work_demand_snapshot.json").read_text(encoding="utf-8"))
    g = json.loads((live_work_dir() / "planning_gaps_snapshot.json").read_text(encoding="utf-8"))
    snaps = {
        "work_demand_snapshot": wd,
        "time_constraints_snapshot": {},
        "daily_progress_snapshot": {},
        "planning_gaps_snapshot": g,
        "communication_queue_snapshot": {},
    }
    a = generate_clickup_action_recommendations(base, snaps, enqueue=False)
    b = compiler_generate(base, snaps, enqueue=False)
    assert a.keys() == b.keys()


def test_proposal_builders_do_not_import_workers() -> None:
    import brain.live_work_orchestration.clickup_actions as ca

    src = Path(ca.__file__).read_text(encoding="utf-8")
    assert "workers" not in src


def test_queue_files_created(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    queue_clickup_action(
        action_type="task_create",
        target_list="Agent Ops",
        target_task_id=None,
        title="T",
        message="m",
        category="other",
        reason="r",
    )
    queue_clarification(message="Q", reason="r")
    assert (tmp_path / "clickup_action_queue.json").is_file()
    assert (tmp_path / "clickup_clarification_queue.json").is_file()
    assert (tmp_path / "clickup_action_log.jsonl").is_file()


def test_corrupt_action_queue_is_not_overwritten(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    queue_path = tmp_path / "clickup_action_queue.json"
    queue_path.write_text('{"generated_at": "t", "items": [', encoding="utf-8")

    with pytest.raises(RuntimeError, match="Refusing to overwrite unreadable queue file"):
        queue_clickup_action(
            action_type="task_create",
            target_list="Agent Ops",
            target_task_id=None,
            title="T",
            message="m",
            category="other",
            reason="r",
        )

    assert queue_path.read_text(encoding="utf-8") == '{"generated_at": "t", "items": ['


def test_corrupt_clarification_queue_is_not_overwritten(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    queue_path = tmp_path / "clickup_clarification_queue.json"
    queue_path.write_text('{"generated_at": "t", "items": [', encoding="utf-8")

    with pytest.raises(RuntimeError, match="Refusing to overwrite unreadable queue file"):
        queue_clarification(message="Q", reason="r")

    assert queue_path.read_text(encoding="utf-8") == '{"generated_at": "t", "items": ['


def test_classify_ambiguous_finance_vs_clarify() -> None:
    cat = classify_work_category("Need clarification for company finance budget")
    assert cat in ("agent_clarifications", "company_finances")
