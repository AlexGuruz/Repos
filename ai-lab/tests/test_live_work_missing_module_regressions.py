from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from brain.live_work_orchestration.compiler import generate_project_timetable
from brain.live_work_orchestration.ingestion.bills import (
    BillRecord,
    build_bills_snapshot,
    evaluate_bill_status,
    summarize_bills_for_planning,
)


def test_bills_module_classifies_overdue_and_upcoming(monkeypatch, tmp_path):
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    today = datetime.now(timezone.utc).date()
    overdue = today - timedelta(days=1)
    upcoming = today + timedelta(days=20)
    bill_file = tmp_path / "manual_bills.json"
    bill_file.write_text(
        json.dumps(
            {
                "bills": [
                    {"name": "Overdue vendor", "due_date": overdue.isoformat(), "amount": "25.50"},
                    {"name": "Upcoming vendor", "due_date": upcoming.isoformat()},
                ]
            }
        ),
        encoding="utf-8",
    )

    assert evaluate_bill_status(BillRecord(name="x", due_date="2026-06-01"), today=date(2026, 6, 2))[
        "status"
    ] == "overdue"

    snapshot = build_bills_snapshot(bill_file)
    summary = summarize_bills_for_planning(snapshot)

    assert len(summary["overdue"]) == 1
    assert len(summary["upcoming"]) == 1
    assert (tmp_path / "ingestion" / "bills_snapshot.json").is_file()


def test_project_timetable_imports_calibration_module(monkeypatch, tmp_path):
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    out = generate_project_timetable(
        repo_activity_snapshot={
            "data": {
                "activity": [
                    {
                        "repo_name": "ai-lab",
                        "likely_feature_name": "planner-lane",
                        "rollout_stage": "review",
                        "activity_intensity": "medium",
                        "changed_files_count": 3,
                        "recent_commits_count": 2,
                        "confidence": 0.7,
                        "evidence": ["local_changes:true"],
                    }
                ]
            }
        },
        github_activity_snapshot={"data": {"feature_states": []}},
        daily_progress_snapshot={"data": {}},
    )

    assert out["status"] == "read_only"
    assert out["calibration_profile"]["sample_count"] == 0
    assert out["timetable"]["rows"]
