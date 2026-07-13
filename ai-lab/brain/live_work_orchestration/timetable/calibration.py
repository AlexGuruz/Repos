from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


def _calibration_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    return root / "state" / "live_work_orchestration" / "calibration" / "estimation_calibration.json"


def _load_records(path: str | Path | None = None) -> list[dict[str, Any]]:
    source = Path(path) if path is not None else _calibration_path()
    if not source.is_file():
        return []
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = raw.get("records") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _duration_hours(row: dict[str, Any]) -> float | None:
    for key in ("actual_hours", "duration_hours", "known_duration_hours"):
        try:
            value = row.get(key)
            if value not in (None, ""):
                hours = float(value)
                return hours if hours > 0 else None
        except Exception:
            continue
    measured = row.get("measured_time")
    if isinstance(measured, dict):
        try:
            hours = float(measured.get("duration_hours"))
            return hours if hours > 0 else None
        except Exception:
            return None
    return None


def _estimate_midpoint(row: dict[str, Any]) -> float | None:
    rng = row.get("estimate_range_hours")
    if isinstance(rng, dict):
        try:
            lo = float(rng.get("min"))
            hi = float(rng.get("max"))
            if lo > 0 and hi >= lo:
                return (lo + hi) / 2.0
        except Exception:
            return None
    try:
        hours = float(row.get("estimated_hours"))
        return hours if hours > 0 else None
    except Exception:
        return None


def build_calibration_profile(records: list[dict[str, Any]] | None) -> dict[str, Any]:
    samples: list[float] = []
    for row in records or []:
        actual = _duration_hours(row)
        estimate = _estimate_midpoint(row)
        if actual is None or estimate is None:
            continue
        samples.append(actual / estimate)
    sample_count = len(samples)
    multiplier = median(samples) if samples else 1.0
    multiplier = max(0.75, min(1.5, float(multiplier)))
    apply = sample_count >= 5 and abs(multiplier - 1.0) >= 0.1
    return {
        "sample_count": sample_count,
        "recommended_adjustments": {
            "apply": apply,
            "hours_multiplier": round(multiplier, 2),
        },
        "confidence": "medium" if apply else "low",
        "notes": "Conservative calibration applies only with at least 5 measured samples.",
    }


def _matching_records(
    records: list[dict[str, Any]] | None,
    feature_name: str,
    repo_name: str,
) -> list[dict[str, Any]]:
    feature_cf = feature_name.strip().lower()
    repo_cf = repo_name.strip().lower()
    out = []
    for row in records or []:
        if str(row.get("feature_name") or "").strip().lower() != feature_cf:
            continue
        if str(row.get("repo_name") or "").strip().lower() != repo_cf:
            continue
        out.append(row)
    return out


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
    for row in _matching_records(existing_records, feature_name, repo_name):
        actual = _duration_hours(row)
        if actual is not None:
            return {
                "selected_source": str(row.get("selected_source") or "user_confirmed_actual"),
                "confidence": str(row.get("confidence") or "medium"),
                "known_duration_hours": actual,
                "measured_time": {"duration_hours": actual},
                "should_ask_user": False,
                "importance_for_prompt": False,
                "reason": "existing_calibration_record",
            }

    should_ask = bool(
        estimate_calibration_needed
        and recently_completed_or_merged
        and str(estimate_risk_level or "").lower() in {"medium", "high"}
    )
    return {
        "selected_source": "unknown_needs_confirmation",
        "confidence": "low",
        "known_duration_hours": None,
        "measured_time": None,
        "should_ask_user": should_ask,
        "importance_for_prompt": should_ask,
        "reason": "no_measured_or_confirmed_actual",
        "repo_activity_present": bool(repo_activity_snapshot),
        "github_activity_present": bool(github_activity_snapshot),
    }


def record_measured_actual_if_confident(
    feature_name: str,
    repo_name: str,
    measured_time: dict[str, Any],
    *,
    path: str | Path | None = None,
) -> dict[str, Any] | None:
    try:
        duration = float(measured_time.get("duration_hours"))
    except Exception:
        return None
    if duration <= 0:
        return None
    source = Path(path) if path is not None else _calibration_path()
    records = _load_records(source)
    record = {
        "feature_name": feature_name,
        "repo_name": repo_name,
        "actual_hours": duration,
        "measured_time": dict(measured_time),
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "selected_source": "measured_actual",
        "confidence": str(measured_time.get("confidence") or "high"),
    }
    records.append(record)
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(json.dumps({"records": records}, indent=2), encoding="utf-8")
    return record


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
        "message": (
            f"How many work hours did {repo_name}/{feature_name} actually take? "
            "A range is OK if exact time is unknown."
        ),
        "reason": str(decision.get("reason") or "calibration_needed"),
        "target_list": "Agent Clarifications",
    }


def summarize_calibration_health(decisions: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = list(decisions or [])
    return {
        "decisions": len(rows),
        "known_actuals": len([d for d in rows if d.get("known_duration_hours") is not None]),
        "questions_needed": len([d for d in rows if d.get("should_ask_user")]),
        "sources": {
            "measured_actual": len([d for d in rows if d.get("selected_source") == "measured_actual"]),
            "inferred_actual": len([d for d in rows if d.get("selected_source") == "inferred_actual"]),
            "user_confirmed_actual": len([d for d in rows if d.get("selected_source") == "user_confirmed_actual"]),
            "unknown_needs_confirmation": len(
                [d for d in rows if d.get("selected_source") == "unknown_needs_confirmation"]
            ),
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
