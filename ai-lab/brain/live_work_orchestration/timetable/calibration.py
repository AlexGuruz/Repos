from __future__ import annotations

import json
from pathlib import Path
from statistics import median
from typing import Any

from brain.prepared_context.schema import now_iso


def _records_path() -> Path:
    from brain.live_work_orchestration.builders import live_work_dir

    return live_work_dir() / "timetable_calibration_records.json"


def _load_records(path: str | Path | None = None) -> list[dict[str, Any]]:
    p = Path(path) if path is not None else _records_path()
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


def build_calibration_profile(records: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = list(records or [])
    ratios: list[float] = []
    for row in rows:
        try:
            estimated = float(row.get("estimated_hours") or 0)
            actual = float(row.get("actual_hours") or row.get("duration_hours") or 0)
        except (TypeError, ValueError):
            continue
        if estimated > 0 and actual > 0:
            ratios.append(actual / estimated)
    multiplier = median(ratios) if ratios else 1.0
    return {
        "sample_count": len(rows),
        "ratio_sample_count": len(ratios),
        "recommended_adjustments": {
            "apply": len(ratios) >= 5,
            "hours_multiplier": round(float(multiplier), 2),
        },
        "generated_at": now_iso(),
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
    records = list(existing_records or [])
    key = (feature_name.strip().lower(), repo_name.strip().lower())
    for row in reversed(records):
        if (
            str(row.get("feature_name") or "").strip().lower(),
            str(row.get("repo_name") or "").strip().lower(),
        ) == key:
            duration = row.get("measured_time") or {
                "duration_hours": row.get("actual_hours") or row.get("duration_hours")
            }
            return {
                "selected_source": "measured_actual",
                "confidence": str(row.get("confidence") or "medium"),
                "known_duration_hours": row.get("actual_hours") or row.get("duration_hours"),
                "measured_time": duration,
                "should_ask_user": False,
                "importance_for_prompt": False,
                "reason": "matched_calibration_record",
            }

    should_ask = bool(estimate_calibration_needed or estimate_risk_level == "high" or recently_completed_or_merged)
    return {
        "selected_source": "unknown_needs_confirmation",
        "confidence": "low",
        "known_duration_hours": None,
        "measured_time": None,
        "should_ask_user": should_ask,
        "importance_for_prompt": should_ask,
        "reason": "no_matching_calibration_record",
        "evidence": [
            f"repo_activity_present:{bool(repo_activity_snapshot)}",
            f"github_activity_present:{bool(github_activity_snapshot)}",
        ],
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
        "message": (
            "Confirm the actual effort or remaining effort range for "
            f"{repo_name}/{feature_name}; current timetable has insufficient calibration evidence."
        ),
    }


def record_measured_actual_if_confident(feature_name: str, repo_name: str, measured_time: dict[str, Any]) -> bool:
    try:
        duration = float(measured_time.get("duration_hours"))
    except (AttributeError, TypeError, ValueError):
        return False
    if duration <= 0:
        return False
    path = _records_path()
    rows = _load_records(path)
    rows.append(
        {
            "feature_name": feature_name,
            "repo_name": repo_name,
            "actual_hours": duration,
            "confidence": str(measured_time.get("confidence") or "medium") if isinstance(measured_time, dict) else "medium",
            "recorded_at": now_iso(),
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"records": rows}, indent=2), encoding="utf-8")
    return True


def summarize_calibration_health(decisions: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = list(decisions or [])
    needs = [d for d in rows if d.get("should_ask_user")]
    known = [
        d
        for d in rows
        if d.get("selected_source") in {"measured_actual", "inferred_actual", "user_confirmed_actual"}
    ]
    return {
        "total": len(rows),
        "known_actuals": len(known),
        "needs_user_confirmation": len(needs),
        "status": "needs_calibration" if needs else "ok",
    }


__all__ = [
    "_load_records",
    "build_calibration_correction_prompt",
    "build_calibration_profile",
    "decide_calibration_source",
    "record_measured_actual_if_confident",
    "summarize_calibration_health",
]
