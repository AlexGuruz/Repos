from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _calibration_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    d = root / "state" / "live_work_orchestration" / "calibration"
    d.mkdir(parents=True, exist_ok=True)
    return d / "estimation_calibration.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_records() -> list[dict[str, Any]]:
    path = _calibration_path()
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = data.get("records") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def _save_records(records: list[dict[str, Any]]) -> None:
    _calibration_path().write_text(
        json.dumps({"updated_at": _utc_now(), "records": records}, indent=2, default=str),
        encoding="utf-8",
    )


def _estimate_midpoint_hours(record: dict[str, Any]) -> float | None:
    rng = record.get("estimate_range_hours")
    if not isinstance(rng, dict):
        return None
    try:
        lo = float(rng.get("min"))
        hi = float(rng.get("max"))
    except (TypeError, ValueError):
        return None
    if lo <= 0 or hi <= 0:
        return None
    return (lo + hi) / 2.0


def build_calibration_profile(records: list[dict[str, Any]]) -> dict[str, Any]:
    ratios: list[float] = []
    for row in records:
        actual = row.get("actual_duration_hours")
        if actual is None and isinstance(row.get("measured_time"), dict):
            actual = row["measured_time"].get("duration_hours")
        midpoint = _estimate_midpoint_hours(row)
        try:
            actual_f = float(actual)
        except (TypeError, ValueError):
            continue
        if midpoint and actual_f > 0:
            ratios.append(actual_f / midpoint)

    sample_count = len(ratios)
    if sample_count < 5:
        multiplier = 1.0
        apply = False
    else:
        avg = sum(ratios) / sample_count
        multiplier = max(0.75, min(1.5, avg))
        apply = abs(multiplier - 1.0) >= 0.1
    return {
        "sample_count": sample_count,
        "recommended_adjustments": {
            "apply": apply,
            "hours_multiplier": round(multiplier, 2),
        },
        "status": "insufficient_history" if sample_count < 5 else "ready",
    }


def _feature_records(feature_name: str, repo_name: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        r
        for r in records
        if str(r.get("feature_name") or "") == feature_name and str(r.get("repo_name") or "") == repo_name
    ]


def _extract_measured_time(*snapshots: dict[str, Any] | None, feature_name: str, repo_name: str) -> dict[str, Any] | None:
    for snap in snapshots:
        if not isinstance(snap, dict):
            continue
        data = snap.get("data") if isinstance(snap.get("data"), dict) else {}
        candidates = []
        for key in ("measured_actuals", "inferred_actuals", "feature_states", "activity"):
            val = data.get(key)
            if isinstance(val, list):
                candidates.extend(x for x in val if isinstance(x, dict))
        for row in candidates:
            if str(row.get("feature_name") or row.get("likely_feature_name") or "") != feature_name:
                continue
            if str(row.get("repo_name") or "") != repo_name:
                continue
            mt = row.get("measured_time") if isinstance(row.get("measured_time"), dict) else None
            if mt and mt.get("duration_hours") is not None:
                return mt
            if row.get("actual_duration_hours") is not None:
                return {"duration_hours": row.get("actual_duration_hours"), "source": row.get("source") or "snapshot"}
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
    measured = _extract_measured_time(
        repo_activity_snapshot,
        github_activity_snapshot,
        feature_name=feature_name,
        repo_name=repo_name,
    )
    if measured:
        return {
            "selected_source": "measured_actual",
            "confidence": "high",
            "measured_time": measured,
            "known_duration_hours": measured.get("duration_hours"),
            "should_ask_user": False,
            "importance_for_prompt": False,
            "reason": "measured_actual_from_activity_snapshot",
        }

    prior = _feature_records(feature_name, repo_name, records)
    if prior:
        last = prior[-1]
        actual = last.get("actual_duration_hours")
        if actual is None and isinstance(last.get("measured_time"), dict):
            actual = last["measured_time"].get("duration_hours")
        if actual is not None:
            return {
                "selected_source": "user_confirmed_actual",
                "confidence": str(last.get("confidence") or "medium"),
                "known_duration_hours": actual,
                "should_ask_user": False,
                "importance_for_prompt": False,
                "reason": "existing_calibration_record",
            }

    should_ask = bool(estimate_calibration_needed and (estimate_risk_level == "high" or recently_completed_or_merged))
    return {
        "selected_source": "unknown_needs_confirmation",
        "confidence": "low",
        "known_duration_hours": None,
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
    if not bool(decision.get("should_ask_user") and decision.get("importance_for_prompt")):
        return None
    return {
        "feature_name": feature_name,
        "repo_name": repo_name,
        "reason": decision.get("reason") or "calibration_needed",
        "message": f"Confirm actual time spent for {repo_name}::{feature_name} before tightening future ranges.",
        "target_list": "Agent Clarifications",
    }


def summarize_calibration_health(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total": len(decisions),
        "known_actuals": len([d for d in decisions if d.get("known_duration_hours") is not None]),
        "questions_needed": len([d for d in decisions if d.get("should_ask_user")]),
        "status": "needs_confirmation" if any(d.get("should_ask_user") for d in decisions) else "ok",
    }


def record_measured_actual_if_confident(feature_name: str, repo_name: str, measured_time: dict[str, Any]) -> bool:
    try:
        duration = float(measured_time.get("duration_hours"))
    except (TypeError, ValueError):
        return False
    if duration <= 0:
        return False
    records = _load_records()
    records.append(
        {
            "feature_name": feature_name,
            "repo_name": repo_name,
            "actual_duration_hours": duration,
            "measured_time": measured_time,
            "confidence": measured_time.get("confidence") or "medium",
            "recorded_at": _utc_now(),
        }
    )
    _save_records(records)
    return True


__all__ = [
    "_load_records",
    "build_calibration_correction_prompt",
    "build_calibration_profile",
    "decide_calibration_source",
    "record_measured_actual_if_confident",
    "summarize_calibration_health",
]
