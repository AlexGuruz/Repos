from __future__ import annotations

import json
from pathlib import Path


def test_live_work_ingestion_package_imports_repo_activity_with_bills() -> None:
    from brain.live_work_orchestration.ingestion import build_bills_snapshot, repo_activity

    assert callable(build_bills_snapshot)
    assert hasattr(repo_activity, "build_repo_activity_snapshot")


def test_bills_snapshot_and_timetable_calibration_paths(monkeypatch, tmp_path: Path) -> None:
    from brain.live_work_orchestration.ingestion.bills import build_bills_snapshot
    from brain.live_work_orchestration.compiler import generate_project_timetable

    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    bills_file = tmp_path / "manual_bills.json"
    bills_file.write_text(
        json.dumps({"bills": [{"name": "Rent", "due_date": "2026-01-05", "amount": "1200"}]}),
        encoding="utf-8",
    )

    bills = build_bills_snapshot(bills_file)
    assert bills["snapshot_type"] == "bills_snapshot"
    assert (tmp_path / "ingestion" / "bills_snapshot.json").is_file()

    timetable = generate_project_timetable(
        repo_activity_snapshot={"data": {"activity": []}},
        github_activity_snapshot={"data": {"feature_states": []}},
        daily_progress_snapshot={"data": {}},
        enqueue_clarifications=False,
    )
    assert timetable["status"] == "read_only"
    assert "calibration_health_summary" in timetable
