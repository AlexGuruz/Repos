from __future__ import annotations

import json
from pathlib import Path

from brain.live_work_orchestration.ingestion import build_bills_snapshot, summarize_bills_for_planning
from brain.live_work_orchestration.timetable.calibration import (
    decide_calibration_source,
    record_measured_actual_if_confident,
)


def test_bills_ingestion_imports_and_builds_empty_snapshot(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)

    snap = build_bills_snapshot()

    assert snap["snapshot_type"] == "bills_snapshot"
    assert snap["data"] == []
    assert "manual_bills" in snap["missing_sources"]
    assert (tmp_path / "ingestion" / "bills_snapshot.json").is_file()


def test_bills_summary_classifies_overdue() -> None:
    snap = {
        "data": [
            {
                "id": "rent",
                "name": "Rent",
                "amount_due": 100.0,
                "due_date": "2000-01-01",
                "status": "unpaid",
            }
        ]
    }

    summary = summarize_bills_for_planning(snap)

    assert [row["id"] for row in summary["overdue"]] == ["rent"]
    assert [row["id"] for row in summary["high_risk"]] == ["rent"]


def test_calibration_infers_duration_from_repo_activity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)
    repo_snap = {
        "data": {
            "activity": [
                {
                    "repo_name": "ai-lab",
                    "likely_feature_name": "planner-lane",
                    "activity_window_start": "2026-01-01T00:00:00Z",
                    "activity_window_end": "2026-01-01T03:30:00Z",
                }
            ]
        }
    }

    decision = decide_calibration_source(
        "planner-lane",
        "ai-lab",
        repo_activity_snapshot=repo_snap,
        github_activity_snapshot={},
        existing_records=[],
        estimate_risk_level="medium",
        estimate_calibration_needed=True,
        recently_completed_or_merged=False,
    )

    assert decision["selected_source"] == "inferred_actual"
    assert decision["known_duration_hours"] == 3.5


def test_calibration_records_measured_actual(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr("brain.live_work_orchestration.builders.live_work_dir", lambda: tmp_path)

    row = record_measured_actual_if_confident(
        "planner-lane",
        "ai-lab",
        {"duration_hours": 2.25, "source": "test"},
    )

    assert row is not None
    data = json.loads((tmp_path / "calibration" / "estimation_calibration.json").read_text(encoding="utf-8"))
    assert data["records"][0]["duration_hours"] == 2.25
