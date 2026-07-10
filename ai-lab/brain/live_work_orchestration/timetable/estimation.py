from __future__ import annotations

from typing import Any


def estimate_feature_effort(feature_state: dict[str, Any]) -> dict[str, Any]:
    """
    Estimate effort as a range only.
    Returns unknown_needs_calibration when evidence is insufficient.
    """
    changed = int(feature_state.get("changed_files_count") or 0)
    commits = int(feature_state.get("recent_commits_count") or 0)
    intensity = str(feature_state.get("activity_intensity") or "low")
    stage = str(feature_state.get("rollout_stage") or "unknown")
    evidence = list(feature_state.get("evidence") or [])

    if changed == 0 and commits == 0 and not evidence:
        return {
            "status": "unknown_needs_calibration",
            "estimate_range_hours": None,
            "confidence": 0.2,
            "risk_level": "high",
            "evidence": [],
            "reason": "insufficient_activity_evidence",
        }

    min_h, max_h = 2, 6
    if intensity == "medium":
        min_h, max_h = 6, 16
    elif intensity == "high":
        min_h, max_h = 16, 40

    # rollout stage adjusts range, still coarse and evidence-based only.
    if stage in ("review", "ready_to_merge"):
        min_h = max(1, min_h // 2)
        max_h = max(min_h + 2, int(max_h * 0.7))
    elif stage == "blocked":
        max_h = int(max_h * 1.25)

    confidence = float(feature_state.get("confidence") or 0.5)
    if changed > 0 and commits > 0:
        confidence = min(0.9, confidence + 0.1)
    risk = "low"
    if stage == "blocked":
        risk = "high"
    elif stage in ("unknown",) or confidence < 0.5:
        risk = "medium"

    return {
        "status": "estimated_range",
        "estimate_range_hours": {"min": int(min_h), "max": int(max_h)},
        "confidence": round(confidence, 2),
        "risk_level": risk,
        "evidence": evidence[:8],
        "reason": "activity_and_stage_heuristic",
    }

