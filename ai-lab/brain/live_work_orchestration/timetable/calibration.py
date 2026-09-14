from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from brain.prepared_context.schema import now_iso


def _calibration_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    d = root / "state" / "live_work_orchestration" / "calibration"
    d.mkdir(parents=True, exist_ok=True)
    return d / "estimation_calibration.json"


def _load_records() -> list[dict[str, Any]]:
    path = _calibration_path()
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = raw.get("records") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return []
    return [dict(r) for r in rows if isinstance(r, dict)]


def _duration_hours(value: Any) -> float | None:
    try:
        hours = float(value)
    except (TypeError, ValueError):
        return None
    if hours <= 0:
        return None
    return hours


def build_calibration_profile(records: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [r for r in list(records or []) if _duration_hours(r.get("duration_hours")) is not None]
    if not rows:
        return {
            "sample_count": 0,
            "recommended_adjustments": {"apply": False, "hours_multiplier": 1.0},
            "confidence": "low",
        }
    durations = sorted(float(r["duration_hours"]) for r in rows)
    median_hours = durations[len(durations) // 2]
    return {
        "sample_count": len(rows),
        "median_duration_hours": median_hours,
        "recommended_adjustments": {"apply": len(rows) >= 5, "hours_multiplier": 1.0},
        "confidence": "medium" if len(rows) >= 5 else "low",
    }


def _find_record(feature_name: str, repo_name: str, records: list[dict[str, Any]]) -> dict[str, Any] | None:
    f = feature_name.strip().lower()
    r = repo_name.strip().lower()
    for row in records:
        if str(row.get("feature_name") or "").strip().lower() != f:
            continue
        if str(row.get("repo_name") or "").strip().lower() != r:
            continue
        if _duration_hours(row.get("duration_hours")) is not None:
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
    records = list(existing_records or [])
    rec = _find_record(feature_name, repo_name, records)
    if rec:
        hours = float(rec["duration_hours"])
        return {
            "selected_source": "measured_actual",
            "confidence": str(rec.get("confidence") or "high"),
            "known_duration_hours": hours,
            "measured_time": {"duration_hours": hours, "source": rec.get("source") or "calibration_record"},
            "should_ask_user": False,
            "importance_for_prompt": False,
            "reason": "existing_calibration_record",
        }

    important = bool(estimate_calibration_needed and (recently_completed_or_merged or estimate_risk_level == "high"))
    return {
        "selected_source": "unknown_needs_confirmation",
        "confidence": "low",
        "known_duration_hours": None,
        "measured_time": None,
        "should_ask_user": important,
        "importance_for_prompt": important,
        "reason": "no_measured_actual_available",
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
        "message": f"Confirm actual time spent for {repo_name}::{feature_name} so future estimates can be calibrated.",
        "reason": decision.get("reason") or "missing_calibration_actual",
    }


def record_measured_actual_if_confident(feature_name: str, repo_name: str, measured_time: dict[str, Any]) -> None:
    hours = _duration_hours(measured_time.get("duration_hours") if isinstance(measured_time, dict) else None)
    if hours is None:
        return
    path = _calibration_path()
    records = _load_records()
    records.append(
        {
            "feature_name": feature_name,
            "repo_name": repo_name,
            "duration_hours": hours,
            "source": measured_time.get("source") or "derived",
            "confidence": measured_time.get("confidence") or "medium",
            "recorded_at": now_iso(),
        }
    )
    path.write_text(
        json.dumps(
            {"generated_at": datetime.now(timezone.utc).isoformat(), "records": records},
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


def summarize_calibration_health(decisions: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = list(decisions or [])
    return {
        "total": len(rows),
        "measured_actual": len([d for d in rows if d.get("selected_source") == "measured_actual"]),
        "needs_confirmation": len([d for d in rows if d.get("selected_source") == "unknown_needs_confirmation"]),
        "questions_recommended": len([d for d in rows if d.get("should_ask_user")]),
    }


__all__ = [
    "_load_records",
    "build_calibration_correction_prompt",
    "build_calibration_profile",
    "decide_calibration_source",
    "record_measured_actual_if_confident",
    "summarize_calibration_health",
]
