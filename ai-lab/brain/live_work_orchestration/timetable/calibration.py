from __future__ import annotations

import json
from statistics import median
from typing import Any

from brain.prepared_context.schema import now_iso


def _records_path():
    from brain.live_work_orchestration.builders import live_work_dir

    return live_work_dir() / "timetable_calibration_records.json"


def _load_records() -> list[dict[str, Any]]:
    p = _records_path()
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = raw.get("records") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def _save_records(records: list[dict[str, Any]]) -> None:
    p = _records_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"generated_at": now_iso(), "records": records}, indent=2), encoding="utf-8")


def _duration_hours(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("duration_hours") or value.get("hours")
    try:
        hours = float(value)
    except (TypeError, ValueError):
        return None
    if hours <= 0:
        return None
    return hours


def build_calibration_profile(records: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = records or []
    ratios: list[float] = []
    for row in rows:
        actual = _duration_hours(row.get("actual_hours") or row.get("duration_hours") or row.get("measured_time"))
        estimated = _duration_hours(row.get("estimated_hours") or row.get("estimate_hours"))
        if actual is not None and estimated is not None and estimated > 0:
            ratios.append(actual / estimated)
    multiplier = median(ratios) if ratios else 1.0
    return {
        "sample_count": len(rows),
        "ratio_sample_count": len(ratios),
        "recommended_adjustments": {
            "apply": len(ratios) >= 5,
            "hours_multiplier": round(multiplier, 2),
        },
    }


def _matching_record(feature_name: str, repo_name: str, records: list[dict[str, Any]]) -> dict[str, Any] | None:
    f = feature_name.strip().lower()
    r = repo_name.strip().lower()
    for row in reversed(records):
        if str(row.get("feature_name") or "").strip().lower() == f and str(row.get("repo_name") or "").strip().lower() == r:
            return row
    return None


def decide_calibration_source(
    feature_name: str,
    repo_name: str,
    *,
    repo_activity_snapshot: dict[str, Any] | None = None,
    github_activity_snapshot: dict[str, Any] | None = None,
    existing_records: list[dict[str, Any]] | None = None,
    estimate_risk_level: str = "",
    estimate_calibration_needed: bool = False,
    recently_completed_or_merged: bool = False,
) -> dict[str, Any]:
    del repo_activity_snapshot, github_activity_snapshot
    records = existing_records or []
    record = _matching_record(feature_name, repo_name, records)
    known = _duration_hours((record or {}).get("actual_hours") or (record or {}).get("duration_hours"))
    if known is not None:
        return {
            "selected_source": "measured_actual",
            "known_duration_hours": known,
            "measured_time": {"duration_hours": known},
            "confidence": "high",
            "reason": "matching_calibration_record",
            "should_ask_user": False,
            "importance_for_prompt": False,
        }

    should_ask = bool(estimate_calibration_needed or str(estimate_risk_level).lower() == "high" or recently_completed_or_merged)
    return {
        "selected_source": "unknown_needs_confirmation" if should_ask else "estimate_only",
        "known_duration_hours": None,
        "measured_time": None,
        "confidence": "low",
        "reason": "no_matching_calibration_record",
        "should_ask_user": should_ask,
        "importance_for_prompt": should_ask,
    }


def record_measured_actual_if_confident(feature_name: str, repo_name: str, measured_time: dict[str, Any]) -> dict[str, Any] | None:
    hours = _duration_hours(measured_time)
    if hours is None:
        return None
    records = _load_records()
    record = {
        "feature_name": feature_name,
        "repo_name": repo_name,
        "actual_hours": hours,
        "source": "derived_confident_measurement",
        "recorded_at": now_iso(),
    }
    records.append(record)
    _save_records(records)
    return record


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
        "message": f"Confirm actual effort for {repo_name} / {feature_name} so future timetable ranges can be calibrated.",
        "reason": decision.get("reason") or "calibration_needed",
        "target_list": "Agent Clarifications",
    }


def summarize_calibration_health(decisions: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = decisions or []
    return {
        "decisions": len(rows),
        "known_actuals": len([d for d in rows if d.get("known_duration_hours") is not None]),
        "questions_needed": len([d for d in rows if d.get("should_ask_user")]),
        "status": "needs_more_history" if any(d.get("should_ask_user") for d in rows) else "ok",
    }


__all__ = [
    "_load_records",
    "build_calibration_correction_prompt",
    "build_calibration_profile",
    "decide_calibration_source",
    "record_measured_actual_if_confident",
    "summarize_calibration_health",
]
