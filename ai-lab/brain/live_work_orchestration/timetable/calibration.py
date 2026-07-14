"""Conservative estimation calibration helpers for live-work timetables."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from brain.prepared_context.schema import now_iso


def _calibration_dir() -> Path:
    from brain.live_work_orchestration.builders import live_work_dir

    d = live_work_dir() / "calibration"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _records_path() -> Path:
    return _calibration_dir() / "estimation_calibration.json"


def _load_records() -> list[dict[str, Any]]:
    path = _records_path()
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = raw.get("records") if isinstance(raw, dict) else raw
    return [r for r in list(rows or []) if isinstance(r, dict)]


def _record_matches(record: dict[str, Any], feature_name: str, repo_name: str) -> bool:
    return (
        str(record.get("feature_name") or "").strip().lower() == feature_name.strip().lower()
        and str(record.get("repo_name") or "").strip().lower() == repo_name.strip().lower()
    )


def build_calibration_profile(records: list[dict[str, Any]]) -> dict[str, Any]:
    ratios: list[float] = []
    for row in records:
        try:
            actual = float(row.get("actual_hours"))
            estimated = float(row.get("estimated_midpoint_hours"))
        except (TypeError, ValueError):
            continue
        if actual > 0 and estimated > 0:
            ratios.append(actual / estimated)
    sample_count = len(ratios)
    multiplier = median(ratios) if ratios else 1.0
    apply = sample_count >= 5 and 0.5 <= multiplier <= 2.0
    return {
        "sample_count": sample_count,
        "median_actual_to_estimate_ratio": multiplier,
        "recommended_adjustments": {
            "apply": apply,
            "hours_multiplier": round(multiplier, 2) if apply else 1.0,
            "reason": "sufficient_history" if apply else "insufficient_history",
        },
    }


def _duration_from_iso(start: Any, end: Any) -> float | None:
    if not start or not end:
        return None
    try:
        a = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    except ValueError:
        return None
    if a.tzinfo is None:
        a = a.replace(tzinfo=timezone.utc)
    if b.tzinfo is None:
        b = b.replace(tzinfo=timezone.utc)
    hours = (b - a).total_seconds() / 3600.0
    return round(hours, 2) if hours > 0 else None


def _repo_activity_rows(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    data = (snapshot or {}).get("data") if isinstance(snapshot, dict) else {}
    return [r for r in list((data or {}).get("activity") or []) if isinstance(r, dict)]


def decide_calibration_source(
    feature_name: str,
    repo_name: str,
    *,
    repo_activity_snapshot: dict[str, Any] | None,
    github_activity_snapshot: dict[str, Any] | None,
    existing_records: list[dict[str, Any]],
    estimate_risk_level: str,
    estimate_calibration_needed: bool,
    recently_completed_or_merged: bool,
) -> dict[str, Any]:
    for row in existing_records:
        if _record_matches(row, feature_name, repo_name):
            actual = row.get("actual_hours")
            if actual is not None:
                return {
                    "selected_source": "user_confirmed_actual",
                    "known_duration_hours": actual,
                    "measured_time": actual,
                    "confidence": "high",
                    "should_ask_user": False,
                    "importance_for_prompt": False,
                    "reason": "existing_calibration_record",
                }

    for row in _repo_activity_rows(repo_activity_snapshot):
        if not _record_matches(
            {"feature_name": row.get("likely_feature_name"), "repo_name": row.get("repo_name")},
            feature_name,
            repo_name,
        ):
            continue
        measured = row.get("combined_activity_hours") or _duration_from_iso(
            row.get("activity_started_at") or row.get("first_commit_at"),
            row.get("activity_last_seen_at") or row.get("last_commit_at"),
        )
        if measured:
            return {
                "selected_source": "measured_actual" if recently_completed_or_merged else "inferred_actual",
                "known_duration_hours": measured,
                "measured_time": measured,
                "confidence": "high" if recently_completed_or_merged else "medium",
                "should_ask_user": False,
                "importance_for_prompt": False,
                "reason": "repo_activity_time_bounds",
            }

    should_ask = bool(estimate_calibration_needed and estimate_risk_level in {"medium", "high"})
    return {
        "selected_source": "unknown_needs_confirmation",
        "known_duration_hours": None,
        "measured_time": None,
        "confidence": "unknown",
        "should_ask_user": should_ask,
        "importance_for_prompt": should_ask,
        "reason": "no_measured_or_confirmed_actual",
    }


def build_calibration_correction_prompt(
    feature_name: str,
    repo_name: str,
    *,
    decision: dict[str, Any],
) -> dict[str, Any] | None:
    if not decision.get("should_ask_user"):
        return None
    return {
        "feature_name": feature_name,
        "repo_name": repo_name,
        "message": f"Confirm actual time spent for {repo_name}/{feature_name} so future timetable ranges can calibrate.",
        "reason": decision.get("reason") or "calibration_needed",
    }


def summarize_calibration_health(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(decisions)
    known = len([d for d in decisions if d.get("known_duration_hours") is not None])
    ask = len([d for d in decisions if d.get("should_ask_user")])
    return {
        "total_features": total,
        "known_actuals": known,
        "questions_needed": ask,
        "status": "healthy" if total and ask == 0 else ("needs_input" if ask else "no_features"),
    }


def record_measured_actual_if_confident(feature_name: str, repo_name: str, measured_hours: Any) -> bool:
    try:
        hours = float(measured_hours)
    except (TypeError, ValueError):
        return False
    if hours <= 0:
        return False
    records = _load_records()
    if any(_record_matches(row, feature_name, repo_name) and row.get("actual_hours") == hours for row in records):
        return False
    records.append(
        {
            "feature_name": feature_name,
            "repo_name": repo_name,
            "actual_hours": hours,
            "source": "measured_repo_activity",
            "recorded_at": now_iso(),
        }
    )
    _records_path().write_text(json.dumps({"records": records}, indent=2), encoding="utf-8")
    return True


__all__ = [
    "_load_records",
    "build_calibration_correction_prompt",
    "build_calibration_profile",
    "decide_calibration_source",
    "record_measured_actual_if_confident",
    "summarize_calibration_health",
]
