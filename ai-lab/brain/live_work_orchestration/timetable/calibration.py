from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from brain.prepared_context.schema import now_iso


def _records_path() -> Path:
    from brain.live_work_orchestration.builders import live_work_dir

    return live_work_dir() / "calibration" / "estimation_calibration.json"


def _load_records(path: str | Path | None = None) -> list[dict[str, Any]]:
    p = Path(path) if path is not None else _records_path()
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = data.get("records") if isinstance(data, dict) else data
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def _write_records(records: list[dict[str, Any]], path: str | Path | None = None) -> None:
    p = Path(path) if path is not None else _records_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"generated_at": now_iso(), "records": records}, indent=2), encoding="utf-8")


def _duration_hours(measured_time: Any) -> float | None:
    if isinstance(measured_time, dict):
        value = measured_time.get("duration_hours")
    else:
        value = measured_time
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out > 0 else None


def build_calibration_profile(records: list[dict[str, Any]] | None) -> dict[str, Any]:
    durations = [
        h
        for h in (
            _duration_hours(r.get("measured_time") or r.get("duration_hours"))
            for r in list(records or [])
            if isinstance(r, dict)
        )
        if h is not None
    ]
    sample_count = len(durations)
    return {
        "sample_count": sample_count,
        "median_duration_hours": sorted(durations)[sample_count // 2] if sample_count else None,
        "recommended_adjustments": {
            "apply": False,
            "hours_multiplier": 1.0,
            "reason": "insufficient_history" if sample_count < 5 else "manual_review_required",
        },
        "status": "insufficient_history" if sample_count < 5 else "available",
    }


def _matching_record(
    records: list[dict[str, Any]] | None,
    feature_name: str,
    repo_name: str,
) -> dict[str, Any] | None:
    feature_key = feature_name.strip().casefold()
    repo_key = repo_name.strip().casefold()
    for rec in reversed(list(records or [])):
        if str(rec.get("feature_name") or "").strip().casefold() != feature_key:
            continue
        if str(rec.get("repo_name") or "").strip().casefold() != repo_key:
            continue
        return rec
    return None


def _parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _infer_measured_time(
    feature_name: str,
    repo_name: str,
    repo_activity_snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    rows = ((repo_activity_snapshot or {}).get("data") or {}).get("activity") or []
    feature_key = feature_name.strip().casefold()
    repo_key = repo_name.strip().casefold()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("repo_name") or "").strip().casefold() != repo_key:
            continue
        likely = str(row.get("likely_feature_name") or row.get("feature_name") or "").strip().casefold()
        if likely and likely != feature_key:
            continue
        start = _parse_dt(row.get("activity_window_start") or row.get("first_commit_time"))
        end = _parse_dt(row.get("activity_window_end") or row.get("last_commit_time"))
        if start is None or end is None or end <= start:
            continue
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
    rec = _matching_record(existing_records, feature_name, repo_name)
    measured = (rec or {}).get("measured_time") if rec else None
    if measured is None and rec is not None:
        measured = rec.get("duration_hours")
    duration = _duration_hours(measured)
    if duration is not None:
        return {
            "selected_source": "measured_actual",
            "confidence": str((rec or {}).get("confidence") or "high"),
            "known_duration_hours": duration,
            "measured_time": measured if isinstance(measured, dict) else {"duration_hours": duration},
            "should_ask_user": False,
            "importance_for_prompt": False,
            "reason": "matched_existing_calibration_record",
        }

    inferred = _infer_measured_time(feature_name, repo_name, repo_activity_snapshot)
    if inferred and recently_completed_or_merged:
        return {
            "selected_source": "inferred_actual",
            "confidence": "medium",
            "known_duration_hours": inferred["duration_hours"],
            "measured_time": inferred,
            "should_ask_user": False,
            "importance_for_prompt": False,
            "reason": "repo_activity_window_for_recent_completion",
        }

    should_ask = bool(estimate_calibration_needed and str(estimate_risk_level).lower() in ("high", "medium"))
    return {
        "selected_source": "unknown_needs_confirmation",
        "confidence": "low",
        "known_duration_hours": None,
        "measured_time": None,
        "should_ask_user": should_ask,
        "importance_for_prompt": should_ask,
        "reason": "no_measured_or_inferred_actual",
    }


def build_calibration_correction_prompt(
    feature_name: str,
    repo_name: str,
    *,
    decision: dict[str, Any],
) -> dict[str, Any] | None:
    if not (decision.get("importance_for_prompt") and decision.get("should_ask_user")):
        return None
    return {
        "feature_name": feature_name,
        "repo_name": repo_name,
        "message": f"Confirm actual time spent for {repo_name}/{feature_name} so future timetable ranges can be calibrated.",
        "reason": str(decision.get("reason") or "calibration_confirmation_needed"),
        "target_list": "Agent Clarifications",
    }


def summarize_calibration_health(decisions: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = list(decisions or [])
    measured_actual = len([d for d in rows if d.get("selected_source") == "measured_actual"])
    inferred_actual = len([d for d in rows if d.get("selected_source") == "inferred_actual"])
    unknown = len([d for d in rows if d.get("selected_source") == "unknown_needs_confirmation"])
    questions = len([d for d in rows if d.get("importance_for_prompt") and d.get("should_ask_user")])
    return {
        "total": len(rows),
        "total_decisions": len(rows),
        "measured_actual": measured_actual,
        "inferred_actual": inferred_actual,
        "unknown_needs_confirmation": unknown,
        "known_actuals": measured_actual + inferred_actual,
        "questions_needed": questions,
        "questions_to_ask": questions,
    }


def record_measured_actual_if_confident(
    feature_name: str,
    repo_name: str,
    measured_time: dict[str, Any],
    *,
    path: str | Path | None = None,
) -> dict[str, Any]:
    duration = _duration_hours(measured_time)
    if duration is None:
        return {"recorded": False, "reason": "invalid_duration"}
    records = _load_records(path)
    records.append(
        {
            "feature_name": feature_name,
            "repo_name": repo_name,
            "measured_time": {**measured_time, "duration_hours": duration},
            "duration_hours": duration,
            "confidence": str(measured_time.get("confidence") or "medium"),
            "recorded_at": now_iso(),
        }
    )
    _write_records(records, path)
    return {"recorded": True, "duration_hours": duration}


__all__ = [
    "_load_records",
    "build_calibration_correction_prompt",
    "build_calibration_profile",
    "decide_calibration_source",
    "record_measured_actual_if_confident",
    "summarize_calibration_health",
]
