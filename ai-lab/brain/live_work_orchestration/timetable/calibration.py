from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from brain.prepared_context.schema import now_iso


def _calibration_path() -> Path:
    try:
        from brain.live_work_orchestration.builders import live_work_dir

        root = live_work_dir()
    except Exception:
        root = Path(__file__).resolve().parents[3] / "state" / "live_work_orchestration"
        root.mkdir(parents=True, exist_ok=True)
    return root / "timetable_calibration_records.json"


def _load_records() -> list[dict[str, Any]]:
    path = _calibration_path()
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(raw, dict):
        raw = raw.get("records") or []
    if not isinstance(raw, list):
        return []
    return [r for r in raw if isinstance(r, dict)]


def _duration_hours(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    from datetime import datetime

    try:
        a = datetime.fromisoformat(start.replace("Z", "+00:00"))
        b = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except Exception:
        return None
    hours = (b - a).total_seconds() / 3600.0
    if hours <= 0:
        return None
    return round(hours, 2)


def _matching_record(feature_name: str, repo_name: str, records: list[dict[str, Any]]) -> dict[str, Any] | None:
    f = feature_name.strip().lower()
    r = repo_name.strip().lower()
    for row in reversed(records):
        if str(row.get("feature_name") or "").strip().lower() == f and str(row.get("repo_name") or "").strip().lower() == r:
            return row
    return None


def _repo_activity_rows(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    data = snapshot.get("data") if isinstance(snapshot, dict) and isinstance(snapshot.get("data"), dict) else {}
    rows = data.get("activity") or data.get("repo_activity_rows") or []
    return [r for r in rows if isinstance(r, dict)]


def build_calibration_profile(records: list[dict[str, Any]]) -> dict[str, Any]:
    ratios: list[float] = []
    for row in records:
        actual = row.get("actual_duration_hours") or row.get("duration_hours")
        estimate = row.get("estimated_hours") or row.get("estimate_hours")
        try:
            actual_f = float(actual)
            estimate_f = float(estimate)
        except (TypeError, ValueError):
            continue
        if actual_f > 0 and estimate_f > 0:
            ratios.append(actual_f / estimate_f)

    sample_count = len(ratios)
    multiplier = round(sum(ratios) / sample_count, 2) if ratios else 1.0
    return {
        "sample_count": sample_count,
        "avg_actual_to_estimate_ratio": multiplier if ratios else None,
        "recommended_adjustments": {
            "apply": sample_count >= 5 and 0.5 <= multiplier <= 2.0,
            "hours_multiplier": multiplier,
        },
        "source": "timetable_calibration_records",
    }


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
    existing = _matching_record(feature_name, repo_name, existing_records)
    if existing:
        hours = existing.get("actual_duration_hours") or existing.get("duration_hours")
        try:
            known_duration_hours = float(hours)
        except (TypeError, ValueError):
            known_duration_hours = None
        if known_duration_hours and known_duration_hours > 0:
            return {
                "selected_source": str(existing.get("source") or "user_confirmed_actual"),
                "confidence": str(existing.get("confidence") or "high"),
                "known_duration_hours": known_duration_hours,
                "measured_time": {"duration_hours": known_duration_hours, "source": "calibration_record"},
                "should_ask_user": False,
                "importance_for_prompt": False,
                "reason": "existing_calibration_record",
            }

    f = feature_name.strip().lower()
    r = repo_name.strip().lower()
    for row in _repo_activity_rows(repo_activity_snapshot):
        row_feature = str(row.get("likely_feature_name") or row.get("feature_name") or "").strip().lower()
        row_repo = str(row.get("repo_name") or "").strip().lower()
        if row_feature != f or row_repo != r:
            continue
        hours = _duration_hours(row.get("activity_window_start"), row.get("activity_window_end"))
        if hours is not None and recently_completed_or_merged:
            return {
                "selected_source": "inferred_actual",
                "confidence": "medium",
                "known_duration_hours": hours,
                "measured_time": {
                    "duration_hours": hours,
                    "selected_source": "inferred_actual",
                    "source": "repo_activity_window",
                    "evidence": [
                        str(row.get("activity_window_start") or ""),
                        str(row.get("activity_window_end") or ""),
                    ],
                },
                "should_ask_user": False,
                "importance_for_prompt": False,
                "reason": "repo_activity_window",
            }

    should_ask = bool(estimate_calibration_needed or estimate_risk_level == "high" or recently_completed_or_merged)
    return {
        "selected_source": "unknown_needs_confirmation",
        "confidence": "low",
        "known_duration_hours": None,
        "measured_time": None,
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
    if not bool(decision.get("should_ask_user")):
        return None
    return {
        "feature_name": feature_name,
        "repo_name": repo_name,
        "reason": decision.get("reason") or "calibration_clarification",
        "message": (
            f"How long did {repo_name}::{feature_name} actually take? "
            "A range is fine; this is used only to calibrate future timetable estimates."
        ),
        "target_list": "Agent Clarifications",
    }


def summarize_calibration_health(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(decisions)
    known = len(
        [
            d
            for d in decisions
            if d.get("selected_source") in ("measured_actual", "inferred_actual", "user_confirmed_actual")
        ]
    )
    needs_questions = len([d for d in decisions if d.get("should_ask_user")])
    return {
        "total_features": total,
        "known_actuals": known,
        "unknown_actuals": max(0, total - known),
        "questions_needed": needs_questions,
        "status": "healthy" if total == 0 or needs_questions == 0 else "needs_calibration",
    }


def record_measured_actual_if_confident(
    feature_name: str,
    repo_name: str,
    measured_time: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        hours = float(measured_time.get("duration_hours"))
    except (AttributeError, TypeError, ValueError):
        return None
    if hours <= 0:
        return None

    selected_source = str(measured_time.get("selected_source") or "")
    if selected_source not in ("measured_actual", "inferred_actual", "user_confirmed_actual"):
        selected_source = "measured_actual"
    record = {
        "feature_name": feature_name,
        "repo_name": repo_name,
        "actual_duration_hours": hours,
        "source": selected_source,
        "source_detail": measured_time.get("source") or selected_source,
        "confidence": measured_time.get("confidence") or "medium",
        "recorded_at": now_iso(),
    }
    records = _load_records()
    records.append(record)
    path = _calibration_path()
    path.write_text(json.dumps({"records": records}, indent=2), encoding="utf-8")
    return record


__all__ = [
    "_load_records",
    "build_calibration_correction_prompt",
    "build_calibration_profile",
    "decide_calibration_source",
    "record_measured_actual_if_confident",
    "summarize_calibration_health",
]
