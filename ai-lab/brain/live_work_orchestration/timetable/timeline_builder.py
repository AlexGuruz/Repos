from __future__ import annotations

from typing import Any


def _timeline_bucket(rollout_stage: str, risk_level: str) -> str:
    stage = (rollout_stage or "unknown").lower()
    risk = (risk_level or "high").lower()
    if stage in ("ready_to_merge", "review") and risk in ("low", "medium"):
        return "next_1_2_days"
    if stage in ("dev", "unknown") and risk != "high":
        return "next_3_7_days"
    return "later_or_blocked"


def build_project_timetable(
    feature_states: list[dict[str, Any]],
    estimates: list[dict[str, Any]],
    daily_progress_snapshot: dict[str, Any] | None,
    calibration_decisions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a read-only project timetable with range-based estimates only."""
    rows: list[dict[str, Any]] = []
    n = len(feature_states)
    decisions = calibration_decisions if calibration_decisions is not None else [{} for _ in range(n)]
    for fs, est, dec in zip(feature_states, estimates, decisions):
        rng = est.get("estimate_range_hours")
        src = str((dec or {}).get("selected_source") or "unknown_needs_confirmation")
        known_h = (dec or {}).get("known_duration_hours")
        if known_h is None and isinstance((dec or {}).get("measured_time"), dict):
            try:
                known_h = float((dec or {})["measured_time"]["duration_hours"])  # type: ignore[index]
            except Exception:
                known_h = None
        actual_known = bool(
            known_h is not None
            and src in ("measured_actual", "inferred_actual", "user_confirmed_actual")
        )
        act_conf = str((dec or {}).get("confidence") or "low")
        should_req = bool((dec or {}).get("importance_for_prompt") and (dec or {}).get("should_ask_user"))
        rows.append(
            {
                "feature_name": fs.get("feature_name"),
                "repo_name": fs.get("repo_name"),
                "feature_area": fs.get("feature_area", "core"),
                "activity_type": fs.get("activity_type", "mixed"),
                "rollout_stage": fs.get("rollout_stage"),
                "timeline_bucket": _timeline_bucket(str(fs.get("rollout_stage") or "unknown"), str(est.get("risk_level") or "high")),
                "estimate_range_hours": rng,
                "confidence": est.get("confidence"),
                "risk_level": est.get("risk_level"),
                "blockers": list(fs.get("blockers") or []),
                "linked_pr": fs.get("linked_pr"),
                "next_action": fs.get("next_action"),
                "evidence": list(est.get("evidence") or []),
                "status": est.get("status"),
                "calibration_used": bool(est.get("calibration_used")),
                "calibration_needed": bool(est.get("calibration_needed")),
                "calibration_source": src,
                "actual_duration_known": actual_known,
                "actual_duration_confidence": act_conf,
                "should_request_calibration": should_req,
                "calibration_reason": (dec or {}).get("reason") or est.get("calibration_reason"),
            }
        )

    high_risk = len([x for x in rows if str(x.get("risk_level")) == "high"])
    unknown = len([x for x in rows if str(x.get("status")).startswith("unknown")])
    ready = len([x for x in rows if str(x.get("rollout_stage")) == "ready_to_merge"])
    blocked = len([x for x in rows if str(x.get("rollout_stage")) == "blocked"])

    return {
        "rows": rows,
        "summary": {
            "total_features": len(rows),
            "ready_to_merge": ready,
            "blocked": blocked,
            "high_risk": high_risk,
            "unknown_needs_calibration": unknown,
            "calibration_used": len([x for x in rows if bool(x.get("calibration_used"))]),
            "calibration_needed": len([x for x in rows if bool(x.get("calibration_needed"))]),
        },
        "notes": "Timetable is range-based and guardrail-constrained; no point estimates.",
    }

