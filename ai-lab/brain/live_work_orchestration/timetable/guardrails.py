from __future__ import annotations

from typing import Any


def apply_estimation_guardrails(feature_state: dict[str, Any], estimate: dict[str, Any]) -> dict[str, Any]:
    """
    Enforce anti-fake-precision rules:
    - no point estimates
    - require confidence/risk/evidence
    - fail to unknown_needs_calibration if data quality is low
    """
    out = dict(estimate)
    r = out.get("estimate_range_hours")
    if r is not None:
        if not isinstance(r, dict) or "min" not in r or "max" not in r:
            out["status"] = "unknown_needs_calibration"
            out["estimate_range_hours"] = None
            out["reason"] = "invalid_range"
            out["confidence"] = min(float(out.get("confidence") or 0.3), 0.3)
            out["risk_level"] = "high"
            return out
        mn = int(r.get("min") or 0)
        mx = int(r.get("max") or 0)
        if mn <= 0 or mx <= 0 or mx <= mn:
            out["status"] = "unknown_needs_calibration"
            out["estimate_range_hours"] = None
            out["reason"] = "non_valid_or_point_range"
            out["confidence"] = min(float(out.get("confidence") or 0.3), 0.3)
            out["risk_level"] = "high"
            return out
        # Minimum width guardrail to avoid fake precision.
        if (mx - mn) < 2:
            out["estimate_range_hours"] = {"min": mn, "max": mn + 2}

    if not out.get("evidence"):
        out["status"] = "unknown_needs_calibration"
        out["estimate_range_hours"] = None
        out["reason"] = "missing_evidence"
        out["confidence"] = min(float(out.get("confidence") or 0.3), 0.3)
        out["risk_level"] = "high"

    out["confidence"] = round(float(out.get("confidence") or 0.2), 2)
    out["risk_level"] = str(out.get("risk_level") or "high")
    return out


def generate_timetable_clarifications(
    feature_states: list[dict[str, Any]],
    estimates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Produce clarification prompts for missing scope/deadline/priority or low confidence.
    Does not execute any external action.
    """
    out: list[dict[str, Any]] = []
    for fs, est in zip(feature_states, estimates):
        conf = float(est.get("confidence") or 0.0)
        unknown = str(est.get("status") or "").startswith("unknown")
        blockers = list(fs.get("blockers") or [])
        needs = unknown or conf < 0.5 or "no_remote_pr" in blockers
        if not needs:
            continue
        out.append(
            {
                "target_list": "Agent Clarifications",
                "message": (
                    f"Clarify scope/deadline/priority for feature '{fs.get('feature_name')}' "
                    f"in repo '{fs.get('repo_name')}'. Current estimate is low-confidence."
                ),
                "reason": "low_confidence_timetable_estimate",
                "feature_name": fs.get("feature_name"),
                "repo_name": fs.get("repo_name"),
                "approval_required": True,
            }
        )
    return out

