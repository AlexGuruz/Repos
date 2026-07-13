from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from typing import Any

from brain.prepared_context.schema import now_iso


def _records_path() -> Path:
    from brain.live_work_orchestration.builders import live_work_dir

    return live_work_dir() / "timetable_calibration_records.json"


def _load_records(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or _records_path()
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = raw.get("records") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return []
    return [dict(r) for r in rows if isinstance(r, dict)]


def _duration_hours(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("duration_hours")
    try:
        hours = float(value)
    except Exception:
        return None
    if hours <= 0:
        return None
    return hours


def build_calibration_profile(records: list[dict[str, Any]]) -> dict[str, Any]:
    durations = [
        h
        for h in (_duration_hours(r.get("duration_hours") or r.get("measured_time")) for r in records)
        if h is not None
    ]
    sample_count = len(durations)
    profile: dict[str, Any] = {
        "sample_count": sample_count,
        "median_duration_hours": median(durations) if durations else None,
        "recommended_adjustments": {"apply": False, "hours_multiplier": 1.0},
    }
    if sample_count >= 5:
        med = float(profile["median_duration_hours"] or 0)
        if med > 16:
            profile["recommended_adjustments"] = {"apply": True, "hours_multiplier": 1.2}
        elif 0 < med < 4:
            profile["recommended_adjustments"] = {"apply": True, "hours_multiplier": 0.85}
    return profile


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
    key = (repo_name.strip().lower(), feature_name.strip().lower())
    for record in existing_records:
        rec_key = (
            str(record.get("repo_name") or "").strip().lower(),
            str(record.get("feature_name") or "").strip().lower(),
        )
        hours = _duration_hours(record.get("duration_hours") or record.get("measured_time"))
        if rec_key == key and hours is not None:
            return {
                "selected_source": "measured_actual",
                "confidence": str(record.get("confidence") or "high"),
                "known_duration_hours": hours,
                "measured_time": {"duration_hours": hours},
                "importance_for_prompt": False,
                "should_ask_user": False,
                "reason": "existing_calibration_record",
            }
    should_ask = bool(estimate_calibration_needed or estimate_risk_level == "high" or recently_completed_or_merged)
    return {
        "selected_source": "unknown_needs_confirmation",
        "confidence": "low",
        "known_duration_hours": None,
        "measured_time": None,
        "importance_for_prompt": should_ask,
        "should_ask_user": should_ask,
        "reason": "no_calibration_record",
    }


def build_calibration_correction_prompt(
    feature_name: str,
    repo_name: str,
    *,
    decision: dict[str, Any],
) -> dict[str, Any] | None:
    if not bool(decision.get("importance_for_prompt") and decision.get("should_ask_user")):
        return None
    return {
        "feature_name": feature_name,
        "repo_name": repo_name,
        "message": f"Confirm actual duration or calibration evidence for {repo_name}::{feature_name}.",
        "reason": str(decision.get("reason") or "calibration_needed"),
        "approval_required": True,
    }


def record_measured_actual_if_confident(feature_name: str, repo_name: str, measured_time: dict[str, Any]) -> dict[str, Any] | None:
    hours = _duration_hours(measured_time)
    if hours is None:
        return None
    p = _records_path()
    records = _load_records(p)
    record = {
        "feature_name": feature_name,
        "repo_name": repo_name,
        "duration_hours": hours,
        "confidence": "high",
        "recorded_at": now_iso(),
    }
    records.append(record)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"records": records}, indent=2), encoding="utf-8")
    return record


def summarize_calibration_health(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    known = len([d for d in decisions if d.get("known_duration_hours") is not None])
    requested = len([d for d in decisions if d.get("importance_for_prompt") and d.get("should_ask_user")])
    return {
        "total_decisions": len(decisions),
        "known_actuals": known,
        "questions_needed": requested,
        "status": "needs_calibration" if requested else "ok",
    }


__all__ = [
    "_load_records",
    "build_calibration_correction_prompt",
    "build_calibration_profile",
    "decide_calibration_source",
    "record_measured_actual_if_confident",
    "summarize_calibration_health",
]
