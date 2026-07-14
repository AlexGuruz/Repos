"""Conservative estimation calibration helpers for live-work timetable previews."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any

from brain.prepared_context.schema import now_iso


def _calibration_dir() -> Path:
    from brain.live_work_orchestration.builders import live_work_dir

    return live_work_dir() / "calibration"


def _records_path() -> Path:
    return _calibration_dir() / "estimation_calibration.json"


def _load_records(path: str | Path | None = None) -> list[dict[str, Any]]:
    p = Path(path) if path is not None else _records_path()
    if not p.is_file():
        return []
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = payload.get("records") if isinstance(payload, dict) else payload
    return [r for r in (rows or []) if isinstance(r, dict)]


def _save_records(records: list[dict[str, Any]]) -> None:
    p = _records_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"generated_at": now_iso(), "records": records}, indent=2), encoding="utf-8")


def _duration_from_window(start: Any, end: Any) -> dict[str, Any] | None:
    try:
        s = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        e = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    except Exception:
        return None
    if s.tzinfo is None:
        s = s.replace(tzinfo=timezone.utc)
    if e.tzinfo is None:
        e = e.replace(tzinfo=timezone.utc)
    hours = (e - s).total_seconds() / 3600.0
    if hours <= 0 or hours > 120:
        return None
    return {
        "duration_hours": round(hours, 2),
        "window_start": s.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "window_end": e.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def build_calibration_profile(records: list[dict[str, Any]]) -> dict[str, Any]:
    ratios: list[float] = []
    for r in records:
        try:
            actual = float(r.get("actual_duration_hours") or r.get("duration_hours") or 0)
        except (TypeError, ValueError):
            actual = 0.0
        est = r.get("estimate_range_hours")
        midpoint = None
        if isinstance(est, dict):
            try:
                midpoint = (float(est.get("min") or 0) + float(est.get("max") or 0)) / 2.0
            except (TypeError, ValueError):
                midpoint = None
        if actual > 0 and midpoint and midpoint > 0:
            ratios.append(actual / midpoint)

    sample_count = len(ratios)
    mult = round(float(median(ratios)), 2) if ratios else 1.0
    apply = sample_count >= 5 and (mult <= 0.8 or mult >= 1.2)
    return {
        "sample_count": sample_count,
        "recommended_adjustments": {
            "apply": apply,
            "hours_multiplier": max(0.5, min(2.0, mult)),
            "basis": "median_actual_to_estimate_midpoint",
        },
    }


def _matching_record(
    feature_name: str,
    repo_name: str,
    records: list[dict[str, Any]],
) -> dict[str, Any] | None:
    fn = feature_name.strip().casefold()
    rn = repo_name.strip().casefold()
    for r in reversed(records):
        if str(r.get("feature_name") or "").strip().casefold() == fn and str(r.get("repo_name") or "").strip().casefold() == rn:
            return r
    return None


def _matching_repo_activity(
    feature_name: str,
    repo_name: str,
    repo_activity_snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    data = repo_activity_snapshot.get("data") if isinstance(repo_activity_snapshot, dict) else {}
    rows = data.get("activity") if isinstance(data, dict) else []
    fn = feature_name.strip().casefold()
    rn = repo_name.strip().casefold()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        row_repo = str(row.get("repo_name") or "").strip().casefold()
        row_feature = str(row.get("likely_feature_name") or row.get("feature_name") or "").strip().casefold()
        if row_repo == rn and row_feature == fn:
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
    records = existing_records or []
    rec = _matching_record(feature_name, repo_name, records)
    if rec:
        try:
            known = float(rec.get("actual_duration_hours") or rec.get("duration_hours") or 0)
        except (TypeError, ValueError):
            known = 0.0
        if known > 0:
            return {
                "selected_source": "user_confirmed_actual",
                "confidence": str(rec.get("confidence") or "high"),
                "known_duration_hours": known,
                "reason": "existing_calibration_record",
                "importance_for_prompt": False,
                "should_ask_user": False,
            }

    row = _matching_repo_activity(feature_name, repo_name, repo_activity_snapshot)
    measured = None
    if row:
        measured = _duration_from_window(row.get("activity_window_start"), row.get("activity_window_end"))
    if measured:
        return {
            "selected_source": "inferred_actual",
            "confidence": "medium" if recently_completed_or_merged else "low",
            "measured_time": measured,
            "reason": "repo_activity_window",
            "importance_for_prompt": False,
            "should_ask_user": False,
        }

    important = estimate_calibration_needed or str(estimate_risk_level).lower() == "high" or recently_completed_or_merged
    return {
        "selected_source": "unknown_needs_confirmation",
        "confidence": "low",
        "reason": "no_measured_or_confirmed_duration",
        "importance_for_prompt": important,
        "should_ask_user": important,
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
        "message": f"What was the actual effort range or duration for {repo_name}::{feature_name}?",
        "reason": decision.get("reason") or "calibration_needed",
        "target_list": "Agent Clarifications",
    }


def summarize_calibration_health(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    by_source: dict[str, int] = {}
    ask_count = 0
    for d in decisions:
        src = str(d.get("selected_source") or "unknown")
        by_source[src] = by_source.get(src, 0) + 1
        if d.get("should_ask_user"):
            ask_count += 1
    return {
        "total": len(decisions),
        "by_source": by_source,
        "questions_needed": ask_count,
        "healthy": ask_count == 0,
    }


def record_measured_actual_if_confident(
    feature_name: str,
    repo_name: str,
    measured_time: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        duration = float(measured_time.get("duration_hours") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    if duration <= 0:
        return None
    records = _load_records()
    record = {
        "feature_name": feature_name,
        "repo_name": repo_name,
        "actual_duration_hours": round(duration, 2),
        "source": "repo_activity_window",
        "recorded_at": now_iso(),
        "measured_time": dict(measured_time),
    }
    records.append(record)
    _save_records(records)
    return record


__all__ = [
    "_load_records",
    "build_calibration_correction_prompt",
    "build_calibration_profile",
    "decide_calibration_source",
    "record_measured_actual_if_confident",
    "summarize_calibration_health",
]
