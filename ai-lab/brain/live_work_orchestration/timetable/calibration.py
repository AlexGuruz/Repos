from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from brain.prepared_context.schema import now_iso


def _calibration_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    return root / "state" / "live_work_orchestration" / "calibration" / "estimation_calibration.json"


def _load_records() -> list[dict[str, Any]]:
    path = _calibration_path()
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(data, dict):
        rows = data.get("records") or []
    else:
        rows = data
    return [r for r in rows if isinstance(r, dict)]


def _duration_hours(value: Any) -> float | None:
    if isinstance(value, dict):
        value = value.get("duration_hours")
    try:
        hours = float(value)
    except (TypeError, ValueError):
        return None
    return hours if hours > 0 else None


def build_calibration_profile(records: list[dict[str, Any]]) -> dict[str, Any]:
    durations = [_duration_hours(r.get("measured_time") or r.get("duration_hours")) for r in records]
    known = [h for h in durations if h is not None]
    sample_count = len(known)
    return {
        "sample_count": sample_count,
        "recommended_adjustments": {
            "apply": False,
            "hours_multiplier": 1.0,
            "reason": "insufficient_history" if sample_count < 5 else "manual_review_required",
        },
    }


def _matching_record(feature_name: str, repo_name: str, records: list[dict[str, Any]]) -> dict[str, Any] | None:
    fn = feature_name.strip().lower()
    rn = repo_name.strip().lower()
    for record in reversed(records):
        if str(record.get("feature_name") or "").strip().lower() != fn:
            continue
        if str(record.get("repo_name") or "").strip().lower() != rn:
            continue
        if _duration_hours(record.get("measured_time") or record.get("duration_hours")) is not None:
            return record
    return None


def _parse_iso(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _derive_measured_time_from_repo(feature_name: str, repo_name: str, repo_activity_snapshot: dict[str, Any]) -> dict[str, Any] | None:
    rows = ((repo_activity_snapshot or {}).get("data") or {}).get("activity") or []
    fn = feature_name.strip().lower()
    rn = repo_name.strip().lower()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("repo_name") or "").strip().lower() != rn:
            continue
        if str(row.get("likely_feature_name") or "").strip().lower() != fn:
            continue
        start = _parse_iso(row.get("combined_activity_window_start") or row.get("file_activity_window_start"))
        end = _parse_iso(row.get("combined_activity_window_end") or row.get("file_activity_window_end"))
        if start is None or end is None or end <= start:
            return None
        return {
            "duration_hours": round((end - start).total_seconds() / 3600.0, 2),
            "source": "repo_activity_window",
            "window_start": start.isoformat().replace("+00:00", "Z"),
            "window_end": end.isoformat().replace("+00:00", "Z"),
        }
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
    del github_activity_snapshot
    records = existing_records or []
    record = _matching_record(feature_name, repo_name, records)
    if record is not None:
        measured = record.get("measured_time") or {"duration_hours": record.get("duration_hours")}
        return {
            "selected_source": "user_confirmed_actual",
            "confidence": str(record.get("confidence") or "high"),
            "known_duration_hours": _duration_hours(measured),
            "measured_time": measured,
            "should_ask_user": False,
            "importance_for_prompt": False,
            "reason": "matched_existing_calibration_record",
        }

    measured = _derive_measured_time_from_repo(feature_name, repo_name, repo_activity_snapshot or {})
    if measured and recently_completed_or_merged:
        return {
            "selected_source": "inferred_actual",
            "confidence": "medium",
            "known_duration_hours": measured["duration_hours"],
            "measured_time": measured,
            "should_ask_user": False,
            "importance_for_prompt": False,
            "reason": "derived_from_repo_activity_window",
        }

    important = estimate_calibration_needed or str(estimate_risk_level).lower() == "high"
    return {
        "selected_source": "unknown_needs_confirmation",
        "confidence": "low",
        "known_duration_hours": None,
        "measured_time": None,
        "should_ask_user": bool(important),
        "importance_for_prompt": bool(important),
        "reason": "no_measured_actual_available",
    }


def build_calibration_correction_prompt(feature_name: str, repo_name: str, *, decision: dict[str, Any]) -> dict[str, Any] | None:
    if not decision.get("should_ask_user"):
        return None
    return {
        "feature_name": feature_name,
        "repo_name": repo_name,
        "reason": decision.get("reason") or "calibration_needed",
        "message": f"How many hours did {repo_name}/{feature_name} actually take?",
        "target_list": "Agent Clarifications",
    }


def record_measured_actual_if_confident(feature_name: str, repo_name: str, measured_time: dict[str, Any]) -> dict[str, Any]:
    hours = _duration_hours(measured_time)
    if hours is None:
        raise ValueError("measured_time.duration_hours must be positive")
    path = _calibration_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    records = _load_records()
    record = {
        "feature_name": feature_name,
        "repo_name": repo_name,
        "measured_time": dict(measured_time, duration_hours=hours),
        "confidence": measured_time.get("confidence") or "medium",
        "recorded_at": now_iso(),
    }
    records.append(record)
    path.write_text(json.dumps({"records": records}, indent=2), encoding="utf-8")
    return record


def summarize_calibration_health(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total": len(decisions),
        "known_actuals": len([d for d in decisions if d.get("known_duration_hours") is not None]),
        "questions_needed": len([d for d in decisions if d.get("should_ask_user")]),
        "sources": {
            source: len([d for d in decisions if d.get("selected_source") == source])
            for source in sorted({str(d.get("selected_source") or "unknown") for d in decisions})
        },
    }


__all__ = [
    "_load_records",
    "build_calibration_correction_prompt",
    "build_calibration_profile",
    "decide_calibration_source",
    "record_measured_actual_if_confident",
    "summarize_calibration_health",
]
