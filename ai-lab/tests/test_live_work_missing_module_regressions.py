from __future__ import annotations

import json
from pathlib import Path


def test_ingestion_package_import_does_not_require_missing_bills_module() -> None:
    from brain.live_work_orchestration.ingestion import repo_activity

    assert hasattr(repo_activity, "collect_repo_activity")


def test_bills_snapshot_and_plan_preview_compile(monkeypatch, tmp_path: Path) -> None:
    from brain.live_work_orchestration.compiler import compile_daily_plan_preview
    from brain.live_work_orchestration.ingestion.bills import build_bills_snapshot

    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    (tmp_path / "ingestion").mkdir(parents=True, exist_ok=True)
    (tmp_path / "ingestion" / "repo_activity_snapshot.json").write_text(
        json.dumps(
            {
                "data": {
                    "activity": [
                        {
                            "repo_name": "ai-lab",
                            "likely_feature_name": "retail-panel",
                            "rollout_stage": "review",
                            "activity_intensity": "medium",
                            "changed_files_count": 4,
                            "recent_commits_count": 2,
                            "confidence": 0.7,
                            "evidence": ["test"],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "ingestion" / "github_activity_snapshot.json").write_text(
        json.dumps({"data": {"feature_states": [], "correlation_summary": {}, "blockers": []}}),
        encoding="utf-8",
    )
    for name in (
        "work_demand_snapshot",
        "time_constraints_snapshot",
        "daily_progress_snapshot",
        "planning_gaps_snapshot",
        "communication_queue_snapshot",
    ):
        (tmp_path / f"{name}.json").write_text(json.dumps({"data": {}, "confidence": 0.8}), encoding="utf-8")

    bills = build_bills_snapshot()
    preview = compile_daily_plan_preview(include_action_recommendations=False)

    assert bills["snapshot_type"] == "bills_snapshot"
    assert "project_timetable" in preview
    assert "financial_warnings" in preview
    assert preview["project_timetable"]["rows"]
