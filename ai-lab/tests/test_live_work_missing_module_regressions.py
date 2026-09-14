from __future__ import annotations


def test_ingestion_package_imports_without_missing_bills_module():
    from brain.live_work_orchestration.ingestion import summarize_bills_for_planning

    summary = summarize_bills_for_planning(None)
    assert summary["upcoming"] == []
    assert summary["overdue"] == []
    assert summary["warnings"] == []


def test_generate_project_timetable_imports_calibration_module():
    from brain.live_work_orchestration.compiler import generate_project_timetable

    out = generate_project_timetable(
        repo_activity_snapshot={"data": {"activity": []}},
        github_activity_snapshot={"data": {"feature_states": []}},
        daily_progress_snapshot={"data": {}},
    )
    assert out["status"] == "read_only"
    assert out["calibration_health_summary"]["total_decisions"] == 0
