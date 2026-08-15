from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _calibration_path() -> Path:
    root = Path(__file__).resolve().parents[3]
    return root / "state" / "live_work_orchestration" / "calibration" / "estimation_calibration.json"


def _load_records(path: str | Path | None = None) -> list[dict[str, Any]]:
    p = Path(path) if path else _calibration_path()
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = data.get("records") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def _save_records(records: list[dict[str, Any]], path: str | Path | None = None) -> None:
    p = Path(path) if path else _calibration_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"records": records}, indent=2), encoding="utf-8")


def build_calibration_profile(records: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [r for r in list(records or []) if isinstance(r, dict)]
    durations: list[float] = []
    for row in rows:
        try:
            value = float(row.get("duration_hours"))
        except Exception:
            continue
        if value > 0:
            durations.append(value)
    return {
        "sample_count": len(durations),
        "recommended_adjustments": {},
        "status": "insufficient_history" if len(durations) < 3 else "available",
        "median_duration_hours": sorted(durations)[len(durations) // 2] if durations else None,
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
    """Pick a conservative calibration source without inventing measured time."""
    for row in existing_records or []:
        if (
            str(row.get("feature_name") or "").lower() == str(feature_name or "").lower()
            and str(row.get("repo_name") or "").lower() == str(repo_name or "").lower()
            and row.get("duration_hours") is not None
        ):
            return {
                "selected_source": "user_confirmed_actual",
                "confidence": "medium",
                "known_duration_hours": row.get("duration_hours"),
                "measured_time": {"duration_hours": row.get("duration_hours"), "source": "calibration_record"},
                "importance_for_prompt": False,
                "should_ask_user": False,
                "reason": "matched_existing_calibration_record",
            }

    should_ask = bool(estimate_calibration_needed or str(estimate_risk_level).lower() == "high")
    return {
        "selected_source": "unknown_needs_confirmation",
        "confidence": "low",
        "known_duration_hours": None,
        "measured_time": None,
        "importance_for_prompt": should_ask,
        "should_ask_user": should_ask and bool(recently_completed_or_merged),
        "reason": "no_measured_or_confirmed_actual",
    }


def build_calibration_correction_prompt(
    feature_name: str,
    repo_name: str,
    *,
    decision: dict[str, Any],
) -> dict[str, Any] | None:
    if not bool((decision or {}).get("should_ask_user")):
        return None
    return {
        "feature_name": feature_name,
        "repo_name": repo_name,
        "message": f"Confirm actual time spent for {repo_name} / {feature_name}.",
        "reason": str((decision or {}).get("reason") or "calibration_needed"),
        "target_list": "Agent Clarifications",
    }


def record_measured_actual_if_confident(
    feature_name: str,
    repo_name: str,
    measured_time: dict[str, Any],
    *,
    path: str | Path | None = None,
) -> bool:
    try:
        duration = float(measured_time.get("duration_hours"))
    except Exception:
        return False
    if duration <= 0:
        return False
    rows = _load_records(path)
    rows.append(
        {
            "feature_name": feature_name,
            "repo_name": repo_name,
            "duration_hours": duration,
            "recorded_at": _now_iso(),
            "source": str(measured_time.get("source") or "derived"),
        }
    )
    _save_records(rows, path)
    return True


def summarize_calibration_health(decisions: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = list(decisions or [])
    return {
        "total_decisions": len(rows),
        "known_actuals": len([r for r in rows if bool(r.get("known_duration_hours") is not None)]),
        "questions_needed": len([r for r in rows if bool(r.get("importance_for_prompt"))]),
        "questions_to_ask": len([r for r in rows if bool(r.get("should_ask_user"))]),
    }


__all__ = [
    "_load_records",
    "build_calibration_correction_prompt",
    "build_calibration_profile",
    "decide_calibration_source",
    "record_measured_actual_if_confident",
    "summarize_calibration_health",
]
