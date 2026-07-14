from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from brain.prepared_context.schema import now_iso


def _calibration_path() -> Path:
    from brain.live_work_orchestration.builders import live_work_dir

    return live_work_dir() / "calibration" / "estimation_calibration.json"


def _load_records() -> list[dict[str, Any]]:
    path = _calibration_path()
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        rows = payload.get("records")
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []


def _save_records(records: list[dict[str, Any]]) -> None:
    path = _calibration_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps({"generated_at": now_iso(), "records": records}, indent=2), encoding="utf-8")
    tmp.replace(path)


def build_calibration_profile(records: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [r for r in (records or []) if isinstance(r, dict)]
    ratios: list[float] = []
    for row in rows:
        try:
            actual = float(row.get("actual_duration_hours") or row.get("duration_hours") or 0)
            estimated = float(row.get("estimated_midpoint_hours") or row.get("estimate_midpoint_hours") or 0)
        except Exception:
            continue
        if actual > 0 and estimated > 0:
            ratios.append(actual / estimated)
    if not ratios:
        multiplier = 1.0
    else:
        ratios = sorted(ratios)
        multiplier = ratios[len(ratios) // 2]
    return {
        "sample_count": len(rows),
        "usable_sample_count": len(ratios),
        "recommended_adjustments": {
            "apply": len(ratios) >= 5,
            "hours_multiplier": round(max(0.5, min(2.0, multiplier)), 2),
        },
    }


def decide_calibration_source(
    feature_name: str,
    repo_name: str,
    *,
    repo_activity_snapshot: dict[str, Any] | None,
    github_activity_snapshot: dict[str, Any] | None,
    existing_records: list[dict[str, Any]] | None,
    estimate_risk_level: str,
    estimate_calibration_needed: bool,
    recently_completed_or_merged: bool,
) -> dict[str, Any]:
    key_feature = (feature_name or "").strip().lower()
    key_repo = (repo_name or "").strip().lower()
    for row in existing_records or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("feature_name") or "").strip().lower() != key_feature:
            continue
        if str(row.get("repo_name") or "").strip().lower() != key_repo:
            continue
        try:
            hours = float(row.get("actual_duration_hours") or row.get("duration_hours"))
        except Exception:
            hours = 0.0
        if hours > 0:
            return {
                "selected_source": "measured_actual",
                "confidence": str(row.get("confidence") or "high"),
                "known_duration_hours": hours,
                "measured_time": {"duration_hours": hours, "source": "calibration_records"},
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
        "reason": "no_measured_or_confirmed_actual",
        "repo_activity_observed": bool(repo_activity_snapshot),
        "github_activity_observed": bool(github_activity_snapshot),
    }


def record_measured_actual_if_confident(feature_name: str, repo_name: str, measured_time: dict[str, Any]) -> None:
    try:
        hours = float(measured_time.get("duration_hours"))
    except Exception:
        return
    if hours <= 0:
        return
    rows = _load_records()
    rows.append(
        {
            "feature_name": feature_name,
            "repo_name": repo_name,
            "actual_duration_hours": hours,
            "confidence": measured_time.get("confidence") or "medium",
            "source": measured_time.get("source") or "derived",
            "recorded_at": now_iso(),
        }
    )
    _save_records(rows)


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
        "message": (
            f"Confirm actual time spent for {repo_name}/{feature_name} so future timetable ranges can be calibrated."
        ),
        "target_list": "Agent Clarifications",
    }


def summarize_calibration_health(decisions: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [d for d in (decisions or []) if isinstance(d, dict)]
    known = [
        d
        for d in rows
        if d.get("selected_source") in ("measured_actual", "inferred_actual", "user_confirmed_actual")
    ]
    asks = [d for d in rows if bool(d.get("importance_for_prompt") and d.get("should_ask_user"))]
    return {
        "features_evaluated": len(rows),
        "actuals_known": len(known),
        "questions_needed": len(asks),
        "status": "needs_calibration" if asks else "ok",
    }


__all__ = [
    "_load_records",
    "build_calibration_correction_prompt",
    "build_calibration_profile",
    "decide_calibration_source",
    "record_measured_actual_if_confident",
    "summarize_calibration_health",
]
