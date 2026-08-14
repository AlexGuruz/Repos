"""Calibration helpers for read-only timetable generation."""
from __future__ import annotations

import json
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
    return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []


def build_calibration_profile(records: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [r for r in (records or []) if isinstance(r, dict)]
    durations: list[float] = []
    for row in rows:
        try:
            val = float(row.get("duration_hours"))
        except (TypeError, ValueError):
            continue
        if val > 0:
            durations.append(val)
    avg = round(sum(durations) / len(durations), 2) if durations else None
    return {
        "sample_count": len(durations),
        "average_duration_hours": avg,
        "recommended_adjustments": {"apply": False, "hours_multiplier": 1.0},
        "status": "insufficient_history" if len(durations) < 5 else "ready",
    }


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
    for row in existing_records or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("feature_name") or "") == feature_name and str(row.get("repo_name") or "") == repo_name:
            try:
                hours = float(row.get("duration_hours"))
            except (TypeError, ValueError):
                hours = 0.0
            if hours > 0:
                return {
                    "selected_source": "user_confirmed_actual",
                    "confidence": "high",
                    "known_duration_hours": hours,
                    "measured_time": {"duration_hours": hours, "source": "calibration_records"},
                    "importance_for_prompt": False,
                    "should_ask_user": False,
                    "reason": "matched_existing_calibration_record",
                }
    should_ask = bool(estimate_calibration_needed or recently_completed_or_merged or estimate_risk_level == "high")
    return {
        "selected_source": "estimate_only",
        "confidence": "low" if should_ask else "medium",
        "known_duration_hours": None,
        "measured_time": None,
        "importance_for_prompt": should_ask,
        "should_ask_user": should_ask,
        "reason": "no_measured_actual_available",
        "repo_activity_present": bool(repo_activity_snapshot),
        "github_activity_present": bool(github_activity_snapshot),
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
        "reason": decision.get("reason") or "calibration_needed",
        "message": f"Confirm actual effort for {repo_name}/{feature_name} when available.",
        "selected_source": decision.get("selected_source"),
    }


def summarize_calibration_health(decisions: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [d for d in (decisions or []) if isinstance(d, dict)]
    needs = [d for d in rows if d.get("importance_for_prompt") and d.get("should_ask_user")]
    known = [
        d
        for d in rows
        if d.get("selected_source") in ("measured_actual", "inferred_actual", "user_confirmed_actual")
    ]
    return {
        "total_decisions": len(rows),
        "known_actuals": len(known),
        "questions_needed": len(needs),
        "status": "needs_calibration" if needs else "ok",
    }


def record_measured_actual_if_confident(feature_name: str, repo_name: str, measured_time: dict[str, Any]) -> dict[str, Any] | None:
    try:
        hours = float(measured_time.get("duration_hours"))
    except (AttributeError, TypeError, ValueError):
        return None
    if hours <= 0:
        return None
    row = {
        "feature_name": feature_name,
        "repo_name": repo_name,
        "duration_hours": hours,
        "recorded_at": now_iso(),
        "source": str(measured_time.get("source") or "derived"),
    }
    p = _records_path()
    records = _load_records()
    records.append(row)
    p.write_text(json.dumps({"records": records}, indent=2), encoding="utf-8")
    return row
