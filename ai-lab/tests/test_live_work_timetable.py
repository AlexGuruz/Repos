from __future__ import annotations

import json
from pathlib import Path

import pytest

from brain.live_work_orchestration.compiler import generate_project_timetable, compile_daily_plan_preview
from brain.live_work_orchestration.timetable.estimation import estimate_feature_effort
from brain.live_work_orchestration.timetable.feature_model import build_feature_states
from brain.live_work_orchestration.timetable.guardrails import (
    apply_estimation_guardrails,
    generate_timetable_clarifications,
)
from brain.live_work_orchestration.timetable.timeline_builder import build_project_timetable


def _repo_snap() -> dict:
    return {
        "data": {
            "activity": [
                {
                    "repo_name": "ai-lab",
                    "likely_feature_name": "planner-lane",
                    "current_branch": "feature/planner-lane",
                    "rollout_stage": "dev",
                    "activity_intensity": "medium",
                    "activity_type": "code",
                    "changed_files_count": 8,
                    "recent_commits_count": 4,
                    "confidence": 0.65,
                    "linked_pr_guess": "branch:feature/planner-lane",
                }
            ]
        }
    }


def _gh_snap() -> dict:
    return {
        "data": {
            "feature_states": [
                {
                    "feature_name": "planner-lane",
                    "repo_name": "ai-lab",
                    "local_activity_present": True,
                    "linked_pr": "https://github.com/acme/ai-lab/pull/12",
                    "issue_refs": ["#88"],
                    "rollout_stage": "review",
                    "blockers": [],
                    "blocker_type": ["unknown"],
                    "next_action": "progress_pr",
                    "confidence": 0.75,
                    "evidence": ["pr_head_match:true"],
                }
            ]
        }
    }


def test_feature_model_builds_states() -> None:
    rows = build_feature_states(_repo_snap(), _gh_snap())
    assert rows
    assert rows[0]["feature_name"] == "planner-lane"


def test_estimation_returns_range_only() -> None:
    fs = build_feature_states(_repo_snap(), _gh_snap())[0]
    est = estimate_feature_effort(fs)
    assert est["estimate_range_hours"] is not None
    assert est["estimate_range_hours"]["max"] > est["estimate_range_hours"]["min"]


def test_guardrails_unknown_when_insufficient() -> None:
    fs = {"feature_name": "x", "repo_name": "r"}
    est = {
        "status": "estimated_range",
        "estimate_range_hours": {"min": 1, "max": 1},
        "confidence": 0.9,
        "risk_level": "low",
        "evidence": [],
    }
    out = apply_estimation_guardrails(fs, est)
    assert out["status"].startswith("unknown")
    assert out["estimate_range_hours"] is None


def test_timeline_builder_outputs_rows_and_summary() -> None:
    fs = build_feature_states(_repo_snap(), _gh_snap())
    estimates = [apply_estimation_guardrails(x, estimate_feature_effort(x)) for x in fs]
    out = build_project_timetable(fs, estimates, {"data": {}})
    assert out["rows"]
    assert "summary" in out


def test_clarification_generation_low_confidence() -> None:
    fs = [{"feature_name": "f", "repo_name": "r", "blockers": ["no_remote_pr"]}]
    est = [{"status": "unknown_needs_calibration", "confidence": 0.3}]
    qs = generate_timetable_clarifications(fs, est)
    assert qs
    assert qs[0]["target_list"] == "Agent Clarifications"


def test_generate_project_timetable_read_only() -> None:
    out = generate_project_timetable(
        repo_activity_snapshot=_repo_snap(),
        github_activity_snapshot=_gh_snap(),
        daily_progress_snapshot={"data": {}},
        enqueue_clarifications=False,
    )
    assert out["status"] == "read_only"
    assert isinstance(out["timetable"]["rows"], list)
    assert out["queued_clarifications"] == []
    assert "calibration_health_summary" in out
    assert "calibration_questions_needed" in out
    row = out["timetable"]["rows"][0]
    assert "calibration_source" in row
    assert "actual_duration_known" in row


def test_calibration_profile_defaults_to_no_adjustment_without_history() -> None:
    from brain.live_work_orchestration.timetable.calibration import build_calibration_profile

    profile = build_calibration_profile([])

    assert profile["sample_count"] == 0
    assert profile["recommended_adjustments"]["apply"] is False


def test_compiler_includes_timetable_signals(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    (tmp_path / "ingestion").mkdir(parents=True, exist_ok=True)
    (tmp_path / "ingestion" / "repo_activity_snapshot.json").write_text(json.dumps(_repo_snap()), encoding="utf-8")
    (tmp_path / "ingestion" / "github_activity_snapshot.json").write_text(json.dumps(_gh_snap()), encoding="utf-8")
    (tmp_path / "work_demand_snapshot.json").write_text(json.dumps({"data": {"demands": []}, "confidence": 0.8}), encoding="utf-8")
    (tmp_path / "time_constraints_snapshot.json").write_text(json.dumps({"data": {"constraints": []}, "confidence": 0.8}), encoding="utf-8")
    (tmp_path / "planning_gaps_snapshot.json").write_text(json.dumps({"data": {"gaps": []}}), encoding="utf-8")
    (tmp_path / "communication_queue_snapshot.json").write_text(json.dumps({"data": {"items": []}}), encoding="utf-8")
    (tmp_path / "daily_progress_snapshot.json").write_text(
        json.dumps(
            {
                "data": {
                    "events": [],
                    "repo_activity_rows": _repo_snap()["data"]["activity"],
                    "repo_activity_ingestion_summary": {"repos_with_activity": 1, "repos_scanned": 1},
                    "github_feature_states": _gh_snap()["data"]["feature_states"],
                    "github_remote_summary": {"local_with_pr_match": 1, "local_without_pr": 0, "open_pr_without_local_activity": 0},
                    "github_blockers": [],
                }
            }
        ),
        encoding="utf-8",
    )
    prev = compile_daily_plan_preview(include_action_recommendations=False)
    assert "project_timetable" in prev
    assert "timetable_estimates" in prev
    assert "timetable_clarifications" in prev

