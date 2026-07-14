"""Conservative timetable calibration helpers.

Calibration is advisory: estimates remain ranges, and measured actuals are only
used when explicit repo/GitHub timing evidence or saved records exist.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from brain.prepared_context.schema import now_iso


def _calibration_dir() -> Path:
    root = Path(__file__).resolve().parents[3]
    d = root / "state" / "live_work_orchestration" / "calibration"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _records_path() -> Path:
    return _calibration_dir() / "estimation_calibration.json"


def _load_records() -> list[dict[str, Any]]:
    path = _records_path()
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = payload.get("records") if isinstance(payload, dict) else payload
    return [x for x in (rows or []) if isinstance(x, dict)] if isinstance(rows, list) else []


def _save_records(records: list[dict[str, Any]]) -> None:
    payload = {"generated_at": now_iso(), "records": records}
    _records_path().write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def _parse_ts(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _duration_hours(start: Any, end: Any) -> float | None:
    s = _parse_ts(start)
    e = _parse_ts(end)
    if not s or not e or e <= s:
        return None
    hours = (e - s).total_seconds() / 3600.0
    if hours <= 0 or hours > 240:
        return None
    return round(hours, 2)


def _find_repo_row(feature_name: str, repo_name: str, snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    data = (snapshot or {}).get("data") if isinstance(snapshot, dict) else {}
    rows = list((data or {}).get("activity") or []) if isinstance(data, dict) else []
    feature_l = feature_name.lower()
    repo_l = repo_name.lower()
    for row in rows:
        if not isinstance(row, dict):
            continue
        row_repo = str(row.get("repo_name") or "").lower()
        row_feature = str(row.get("likely_feature_name") or row.get("repo_name") or "").lower()
        if row_repo == repo_l and row_feature == feature_l:
            return row
    return None


def _find_github_state(feature_name: str, repo_name: str, snapshot: dict[str, Any] | None) -> dict[str, Any] | None:
    data = (snapshot or {}).get("data") if isinstance(snapshot, dict) else {}
    rows = list((data or {}).get("feature_states") or []) if isinstance(data, dict) else []
    feature_l = feature_name.lower()
    repo_l = repo_name.lower()
    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("repo_name") or "").lower() == repo_l and str(row.get("feature_name") or "").lower() == feature_l:
            return row
    return None


def _record_matches(record: dict[str, Any], feature_name: str, repo_name: str) -> bool:
    return (
        str(record.get("feature_name") or "").lower() == feature_name.lower()
        and str(record.get("repo_name") or "").lower() == repo_name.lower()
    )


def _known_record_duration(record: dict[str, Any]) -> float | None:
    for key in ("actual_duration_hours", "duration_hours", "known_duration_hours"):
        try:
            value = float(record.get(key))
            if value > 0:
                return round(value, 2)
        except Exception:
            pass
    return None


def build_calibration_profile(records: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [r for r in (records or []) if _known_record_duration(r) is not None]
    ratios: list[float] = []
    for row in rows:
        actual = _known_record_duration(row)
        est = row.get("estimated_range_hours")
        midpoint = None
        if isinstance(est, dict):
            try:
                midpoint = (float(est.get("min")) + float(est.get("max"))) / 2.0
            except Exception:
                midpoint = None
        if actual and midpoint and midpoint > 0:
            ratios.append(actual / midpoint)
    avg_ratio = round(sum(ratios) / len(ratios), 2) if ratios else None
    apply = bool(avg_ratio is not None and len(ratios) >= 5 and 0.5 <= avg_ratio <= 2.0)
    return {
        "sample_count": len(rows),
        "ratio_sample_count": len(ratios),
        "average_actual_to_estimate_ratio": avg_ratio,
        "recommended_adjustments": {
            "apply": apply,
            "hours_multiplier": avg_ratio if apply else 1.0,
        },
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
    matching_records = [r for r in (existing_records or []) if _record_matches(r, feature_name, repo_name)]
    for record in reversed(matching_records):
        duration = _known_record_duration(record)
        if duration is not None:
            return {
                "selected_source": "user_confirmed_actual",
                "confidence": str(record.get("confidence") or "high"),
                "known_duration_hours": duration,
                "measured_time": {"duration_hours": duration, "source": "calibration_record"},
                "importance_for_prompt": False,
                "should_ask_user": False,
                "reason": "matched_saved_calibration_record",
            }

    repo_row = _find_repo_row(feature_name, repo_name, repo_activity_snapshot)
    duration = None
    if repo_row:
        duration = _duration_hours(repo_row.get("activity_window_start"), repo_row.get("activity_window_end"))
        if duration is None:
            duration = _duration_hours(repo_row.get("first_commit_time"), repo_row.get("last_commit_time"))
    if duration is not None:
        return {
            "selected_source": "measured_actual",
            "confidence": "high" if recently_completed_or_merged else "medium",
            "known_duration_hours": duration,
            "measured_time": {"duration_hours": duration, "source": "repo_activity_window"},
            "importance_for_prompt": False,
            "should_ask_user": False,
            "reason": "derived_from_repo_activity_window",
        }

    gh_state = _find_github_state(feature_name, repo_name, github_activity_snapshot)
    if gh_state and recently_completed_or_merged:
        duration = _duration_hours(gh_state.get("created_at"), gh_state.get("merged_at") or gh_state.get("updated_at"))
        if duration is not None:
            return {
                "selected_source": "inferred_actual",
                "confidence": "medium",
                "known_duration_hours": duration,
                "measured_time": {"duration_hours": duration, "source": "github_pr_lifecycle"},
                "importance_for_prompt": False,
                "should_ask_user": False,
                "reason": "inferred_from_github_lifecycle",
            }

    risk = str(estimate_risk_level or "").lower()
    should_ask = bool(estimate_calibration_needed and risk in {"high", "medium"})
    return {
        "selected_source": "unknown_needs_confirmation",
        "confidence": "low",
        "known_duration_hours": None,
        "measured_time": None,
        "importance_for_prompt": should_ask,
        "should_ask_user": should_ask,
        "reason": "no_measured_or_confirmed_actual",
    }


def build_calibration_correction_prompt(
    feature_name: str,
    repo_name: str,
    *,
    decision: dict[str, Any],
) -> dict[str, Any] | None:
    if not bool((decision or {}).get("importance_for_prompt") and (decision or {}).get("should_ask_user")):
        return None
    return {
        "target_list": "Agent Clarifications",
        "message": (
            f"Confirm actual time spent for feature '{feature_name}' in repo '{repo_name}' "
            "so future timetable ranges can be calibrated."
        ),
        "reason": "missing_estimation_actual",
        "feature_name": feature_name,
        "repo_name": repo_name,
        "approval_required": True,
    }


def summarize_calibration_health(decisions: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [d for d in (decisions or []) if isinstance(d, dict)]
    known = [d for d in rows if d.get("known_duration_hours") is not None]
    prompts = [d for d in rows if bool(d.get("importance_for_prompt") and d.get("should_ask_user"))]
    by_source: dict[str, int] = {}
    for row in rows:
        src = str(row.get("selected_source") or "unknown")
        by_source[src] = by_source.get(src, 0) + 1
    return {
        "total_features": len(rows),
        "actual_duration_known": len(known),
        "calibration_questions_needed": len(prompts),
        "source_counts": by_source,
    }


def record_measured_actual_if_confident(
    feature_name: str,
    repo_name: str,
    measured_time: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        duration = float((measured_time or {}).get("duration_hours"))
    except Exception:
        return None
    if duration <= 0:
        return None
    record = {
        "feature_name": feature_name,
        "repo_name": repo_name,
        "actual_duration_hours": round(duration, 2),
        "source": str((measured_time or {}).get("source") or "measured_time"),
        "recorded_at": now_iso(),
        "confidence": str((measured_time or {}).get("confidence") or "medium"),
    }
    records = _load_records()
    records.append(record)
    _save_records(records)
    return record
