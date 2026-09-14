from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from brain.prepared_context.schema import now_iso


def _live_work_dir() -> Path:
    try:
        from brain.live_work_orchestration.builders import live_work_dir

        return live_work_dir()
    except Exception:
        root = Path(__file__).resolve().parents[3]
        d = root / "state" / "live_work_orchestration"
        d.mkdir(parents=True, exist_ok=True)
        return d


def _records_path() -> Path:
    return _live_work_dir() / "calibration" / "estimation_calibration.json"


def _load_records() -> list[dict[str, Any]]:
    p = _records_path()
    if not p.is_file():
        return []
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = payload.get("records") if isinstance(payload, dict) else payload
    return [r for r in (rows or []) if isinstance(r, dict)] if isinstance(rows, list) else []


def _parse_dt(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _record_matches(record: dict[str, Any], feature_name: str, repo_name: str) -> bool:
    return (
        str(record.get("feature_name") or "").casefold() == feature_name.casefold()
        and str(record.get("repo_name") or "").casefold() == repo_name.casefold()
    )


def _duration_from_record(record: dict[str, Any]) -> dict[str, Any] | None:
    raw = record.get("measured_time") if isinstance(record.get("measured_time"), dict) else record
    try:
        hours = float(raw.get("duration_hours"))  # type: ignore[union-attr]
    except Exception:
        hours = 0.0
    if hours <= 0:
        return None
    return {
        "duration_hours": hours,
        "source": str(raw.get("source") or record.get("source") or "calibration_record"),  # type: ignore[union-attr]
        "recorded_at": str(record.get("recorded_at") or record.get("created_at") or now_iso()),
    }


def _iter_feature_rows(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    data = (snapshot or {}).get("data") if isinstance(snapshot, dict) else {}
    rows: list[dict[str, Any]] = []
    if isinstance(data, dict):
        for key in ("activity", "feature_states"):
            rows.extend([r for r in list(data.get(key) or []) if isinstance(r, dict)])
    return rows


def _derive_from_repo_activity(
    feature_name: str,
    repo_name: str,
    repo_activity_snapshot: dict[str, Any] | None,
) -> dict[str, Any] | None:
    for row in _iter_feature_rows(repo_activity_snapshot):
        row_feature = str(row.get("likely_feature_name") or row.get("feature_name") or "")
        row_repo = str(row.get("repo_name") or "")
        if row_feature.casefold() != feature_name.casefold() or row_repo.casefold() != repo_name.casefold():
            continue
        start = _parse_dt(row.get("activity_window_start") or row.get("first_commit_time"))
        end = _parse_dt(row.get("activity_window_end") or row.get("last_commit_time"))
        if start and end and end >= start:
            hours = max(0.1, round((end - start).total_seconds() / 3600.0, 2))
            return {
                "duration_hours": hours,
                "source": "repo_activity_window",
                "recorded_at": str(row.get("activity_window_end") or now_iso()),
            }
    return None


def build_calibration_profile(records: list[dict[str, Any]] | None) -> dict[str, Any]:
    usable = [d for r in list(records or []) if (d := _duration_from_record(r))]
    hours = [float(r["duration_hours"]) for r in usable]
    sample_count = len(hours)
    avg = round(sum(hours) / sample_count, 2) if sample_count else None
    multiplier = 1.0
    apply = False
    if sample_count >= 5 and avg is not None:
        if avg >= 10:
            multiplier = 1.15
            apply = True
        elif avg <= 2:
            multiplier = 0.9
            apply = True
    return {
        "sample_count": sample_count,
        "average_duration_hours": avg,
        "recommended_adjustments": {
            "apply": apply,
            "hours_multiplier": multiplier,
            "reason": "sufficient_history" if apply else "insufficient_history",
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
    for record in list(existing_records or []):
        if _record_matches(record, feature_name, repo_name):
            measured = _duration_from_record(record)
            if measured:
                return {
                    "selected_source": "measured_actual",
                    "confidence": "high",
                    "measured_time": measured,
                    "known_duration_hours": measured["duration_hours"],
                    "importance_for_prompt": False,
                    "should_ask_user": False,
                    "reason": "matched_calibration_record",
                }

    inferred = _derive_from_repo_activity(feature_name, repo_name, repo_activity_snapshot)
    if inferred:
        return {
            "selected_source": "inferred_actual",
            "confidence": "medium",
            "measured_time": inferred,
            "known_duration_hours": inferred["duration_hours"],
            "importance_for_prompt": False,
            "should_ask_user": False,
            "reason": "derived_from_repo_activity_window",
        }

    important = (
        estimate_calibration_needed
        or recently_completed_or_merged
        or str(estimate_risk_level or "").lower() == "high"
    )
    return {
        "selected_source": "unknown_needs_confirmation",
        "confidence": "low",
        "measured_time": None,
        "known_duration_hours": None,
        "importance_for_prompt": important,
        "should_ask_user": important,
        "reason": "no_measured_or_inferred_actual",
    }


def record_measured_actual_if_confident(
    feature_name: str,
    repo_name: str,
    measured_time: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        hours = float(measured_time.get("duration_hours"))
    except Exception:
        return None
    if hours <= 0:
        return None
    row = {
        "feature_name": feature_name,
        "repo_name": repo_name,
        "duration_hours": hours,
        "source": str(measured_time.get("source") or "compiler"),
        "recorded_at": str(measured_time.get("recorded_at") or now_iso()),
    }
    p = _records_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = [r for r in _load_records() if not _record_matches(r, feature_name, repo_name)]
    rows.append(row)
    p.write_text(json.dumps({"records": rows}, indent=2), encoding="utf-8")
    return row


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
        "message": f"Confirm actual time spent for {repo_name}/{feature_name} so future timetable ranges can be calibrated.",
        "reason": str(decision.get("reason") or "calibration_unknown"),
        "importance_for_prompt": True,
    }


def summarize_calibration_health(decisions: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = list(decisions or [])
    return {
        "total_decisions": len(rows),
        "measured_actual": len([r for r in rows if r.get("selected_source") == "measured_actual"]),
        "inferred_actual": len([r for r in rows if r.get("selected_source") == "inferred_actual"]),
        "unknown_needs_confirmation": len(
            [r for r in rows if r.get("selected_source") == "unknown_needs_confirmation"]
        ),
        "questions_needed": len([r for r in rows if r.get("should_ask_user")]),
    }
