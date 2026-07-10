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
) -> dict[str, Any]:
    """Build a read-only project timetable with range-based estimates only."""
    rows: list[dict[str, Any]] = []
    for fs, est in zip(feature_states, estimates):
        rng = est.get("estimate_range_hours")
        rows.append(
            {
                "feature_name": fs.get("feature_name"),
                "repo_name": fs.get("repo_name"),
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
        },
        "notes": "Timetable is range-based and guardrail-constrained; no point estimates.",
    }

