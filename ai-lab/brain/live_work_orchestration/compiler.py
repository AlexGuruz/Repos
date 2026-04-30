"""
Read-only daily plan preview compiler (Phase 9–12).

Does not create ClickUp tasks, post comments, update statuses, or write calendar events.
"""
from __future__ import annotations

import json
from typing import Any

from brain.prepared_context.schema import now_iso

from brain.live_work_orchestration.schema import DailyPlanPreview


def _load_live_snapshot(name: str) -> dict[str, Any] | None:
    from brain.live_work_orchestration.builders import live_work_dir

    p = live_work_dir() / f"{name}.json"
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def generate_clickup_action_recommendations(
    plan_preview: dict[str, Any],
    snapshots: dict[str, Any],
    *,
    clickup_tool_available: bool = False,
    enqueue: bool = False,
) -> dict[str, Any]:
    """Delegate to ``clickup_actions`` — plan-shaped ClickUp proposals only (no execution)."""
    from brain.live_work_orchestration.clickup_actions import (
        generate_clickup_action_recommendations as _generate,
    )

    return _generate(
        plan_preview,
        snapshots,
        clickup_tool_available=clickup_tool_available,
        enqueue=enqueue,
    )


def compile_daily_plan_preview(
    *,
    work_demand_snapshot: dict[str, Any] | None = None,
    time_constraints_snapshot: dict[str, Any] | None = None,
    daily_progress_snapshot: dict[str, Any] | None = None,
    planning_gaps_snapshot: dict[str, Any] | None = None,
    communication_queue_snapshot: dict[str, Any] | None = None,
    include_action_recommendations: bool = True,
) -> dict[str, Any]:
    """
    Combine work demand + time constraints + progress (+ optional gaps/queue) into a preview dict.

    Preview-only: returns serialized DailyPlanPreview. No external I/O beyond reading snapshot dicts/files.
    """
    wd = work_demand_snapshot or _load_live_snapshot("work_demand_snapshot") or {}
    tc = time_constraints_snapshot or _load_live_snapshot("time_constraints_snapshot") or {}
    pr = daily_progress_snapshot or _load_live_snapshot("daily_progress_snapshot") or {}
    gaps = planning_gaps_snapshot or _load_live_snapshot("planning_gaps_snapshot") or {}
    cq = communication_queue_snapshot or _load_live_snapshot("communication_queue_snapshot") or {}

    demands = (wd.get("data") or {}).get("demands") or []
    constraints = (tc.get("data") or {}).get("constraints") or []
    pr_data = pr.get("data") if isinstance(pr.get("data"), dict) else {}
    events = pr_data.get("events") or []
    repo_activity_rows = pr_data.get("repo_activity_rows") or []
    repo_activity_summary = pr_data.get("repo_activity_ingestion_summary") or {}
    github_feature_states = pr_data.get("github_feature_states") or []
    github_remote_summary = pr_data.get("github_remote_summary") or {}
    github_blockers = pr_data.get("github_blockers") or []
    gap_list = (gaps.get("data") or {}).get("gaps") or []

    prio_lines = [str(d.get("title") or d.get("notes")) for d in demands[:8]]
    con_lines = [str(c.get("notes") or c.get("label")) for c in constraints[:10]]
    risk_lines = [str(g.get("notes")) for g in gap_list[:6]]
    if wd.get("missing_sources"):
        risk_lines.append(f"Missing sources (do not guess): {wd.get('missing_sources')}")
    if tc.get("missing_sources"):
        risk_lines.append(f"Time snapshot gaps: {tc.get('missing_sources')}")
    if isinstance(repo_activity_summary, dict) and int(repo_activity_summary.get("repos_with_activity") or 0) > 0:
        planned_text = " ".join(prio_lines).lower()
        mismatch = False
        for row in repo_activity_rows:
            if not isinstance(row, dict):
                continue
            feature = str(row.get("likely_feature_name") or "").lower()
            if feature and feature not in planned_text:
                mismatch = True
                break
        if mismatch:
            risk_lines.append(
                "Planned vs actual mismatch signal: recent repo activity suggests work streams not explicitly listed in planned priorities."
            )
    if github_blockers:
        risk_lines.append(f"GitHub blockers detected: {len(github_blockers)} feature(s) have PR/issue blockers.")
    ready_to_merge = len(
        [x for x in github_feature_states if isinstance(x, dict) and str(x.get("rollout_stage")) == "ready_to_merge"]
    )
    if ready_to_merge:
        risk_lines.append(f"{ready_to_merge} feature(s) appear ready to merge and may need review/merge attention.")

    today = " — ".join(prio_lines[:5]) if prio_lines else "(No prioritized items in work demand snapshot.)"
    before_shift = "Light prep: review top priorities and calendar blocks from snapshot only."
    during_shift = "Focus blocks: " + (today[:400] if today else "undefined") + " | Progress events: " + str(len(events))
    if isinstance(repo_activity_summary, dict):
        during_shift += (
            " | Repo activity: "
            f"{repo_activity_summary.get('repos_with_activity', 0)}/{repo_activity_summary.get('repos_scanned', 0)} repos active"
        )
    if isinstance(github_remote_summary, dict):
        during_shift += (
            " | GitHub: "
            f"{github_remote_summary.get('local_with_pr_match', 0)} matched, "
            f"{github_remote_summary.get('local_without_pr', 0)} local w/o PR, "
            f"{github_remote_summary.get('open_pr_without_local_activity', 0)} stale open PR"
        )
    after_shift = "Capture outcomes in repo/docs or personal ops digest when available (manual)."
    top_p = "\n".join(f"- {p}" for p in prio_lines) or "- (none)"
    cons = "\n".join(f"- {c}" for c in con_lines) or "- (none — calendar may be empty)"
    risks = "\n".join(f"- {r}" for r in risk_lines) or "- (none identified)"
    good_day = "Top priorities touched, constraints respected, no speculative commitments without evidence."

    preview_id = f"preview-{now_iso()}"
    observed = now_iso()
    created = now_iso()
    snapshots_bundle = {
        "work_demand_snapshot": wd,
        "time_constraints_snapshot": tc,
        "daily_progress_snapshot": pr,
        "planning_gaps_snapshot": gaps,
        "communication_queue_snapshot": cq,
    }
    plan_for_rec: dict[str, Any] = {
        "id": preview_id,
        "source": "compile_daily_plan_preview",
        "confidence": min(float(wd.get("confidence") or 0.5), float(tc.get("confidence") or 0.5)),
        "observed_at": observed,
        "created_at": created,
        "notes": "Read-only preview. No ClickUp/calendar mutations from this compiler path.",
        "evidence": ["work_demand_snapshot", "time_constraints_snapshot", "daily_progress_snapshot"],
        "status": "open",
        "today": today,
        "before_shift": before_shift,
        "during_shift": during_shift,
        "after_shift": after_shift,
        "top_priorities": top_p,
        "constraints": cons,
        "risks_to_watch": risks,
        "a_good_day_looks_like": good_day,
    }

    proposed: list[dict[str, Any]] = []
    pending_clar: list[dict[str, Any]] = []
    rec: dict[str, Any] | None = None
    if include_action_recommendations:
        rec = generate_clickup_action_recommendations(
            plan_for_rec,
            snapshots_bundle,
            clickup_tool_available=False,
            enqueue=False,
        )
        proposed = list(rec.get("proposed_clickup_actions") or [])
        pending_clar = list(rec.get("pending_clarifications") or [])

    preview = DailyPlanPreview(
        id=preview_id,
        source="compile_daily_plan_preview",
        confidence=float(plan_for_rec["confidence"]),
        observed_at=observed,
        created_at=created,
        notes=str(plan_for_rec["notes"]),
        evidence=list(plan_for_rec["evidence"]),
        status="open",
        today=today,
        before_shift=before_shift,
        during_shift=during_shift,
        after_shift=after_shift,
        top_priorities=top_p,
        constraints=cons,
        risks_to_watch=risks,
        a_good_day_looks_like=good_day,
        proposed_clickup_actions=proposed,
        pending_clarifications=pending_clar,
    )
    out = preview.to_dict()
    if include_action_recommendations and rec is not None:
        out["clickup_action_recommendations"] = rec
    return out
