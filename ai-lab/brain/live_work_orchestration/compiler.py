"""
Read-only daily plan preview compiler (Phase 9).

Does not create Asana tasks, send Slack messages, or write calendar events.
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


def compile_daily_plan_preview(
    *,
    work_demand_snapshot: dict[str, Any] | None = None,
    time_constraints_snapshot: dict[str, Any] | None = None,
    daily_progress_snapshot: dict[str, Any] | None = None,
    planning_gaps_snapshot: dict[str, Any] | None = None,
    communication_queue_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Combine work demand + time constraints + progress (+ optional gaps/queue) into a preview dict.

    Preview-only: returns serialized DailyPlanPreview. No external I/O beyond reading snapshot dicts/files.
    """
    wd = work_demand_snapshot or _load_live_snapshot("work_demand_snapshot") or {}
    tc = time_constraints_snapshot or _load_live_snapshot("time_constraints_snapshot") or {}
    pr = daily_progress_snapshot or _load_live_snapshot("daily_progress_snapshot") or {}
    gaps = planning_gaps_snapshot or _load_live_snapshot("planning_gaps_snapshot") or {}
    _ = communication_queue_snapshot or _load_live_snapshot("communication_queue_snapshot")

    demands = (wd.get("data") or {}).get("demands") or []
    constraints = (tc.get("data") or {}).get("constraints") or []
    events = (pr.get("data") or {}).get("events") or []
    gap_list = (gaps.get("data") or {}).get("gaps") or []

    prio_lines = [str(d.get("title") or d.get("notes")) for d in demands[:8]]
    con_lines = [str(c.get("notes") or c.get("label")) for c in constraints[:10]]
    risk_lines = [str(g.get("notes")) for g in gap_list[:6]]
    if wd.get("missing_sources"):
        risk_lines.append(f"Missing sources (do not guess): {wd.get('missing_sources')}")
    if tc.get("missing_sources"):
        risk_lines.append(f"Time snapshot gaps: {tc.get('missing_sources')}")

    today = " — ".join(prio_lines[:5]) if prio_lines else "(No prioritized items in work demand snapshot.)"
    before_shift = "Light prep: review top priorities and calendar blocks from snapshot only."
    during_shift = "Focus blocks: " + (today[:400] if today else "undefined") + " | Progress events: " + str(len(events))
    after_shift = "Capture outcomes in repo/docs or personal ops digest when available (manual)."
    top_p = "\n".join(f"- {p}" for p in prio_lines) or "- (none)"
    cons = "\n".join(f"- {c}" for c in con_lines) or "- (none — calendar may be empty)"
    risks = "\n".join(f"- {r}" for r in risk_lines) or "- (none identified)"
    good_day = "Top priorities touched, constraints respected, no speculative commitments without evidence."

    preview = DailyPlanPreview(
        id=f"preview-{now_iso()}",
        source="compile_daily_plan_preview",
        confidence=min(float(wd.get("confidence") or 0.5), float(tc.get("confidence") or 0.5)),
        observed_at=now_iso(),
        created_at=now_iso(),
        notes="Read-only preview. No Asana/Slack/calendar mutations.",
        evidence=["work_demand_snapshot", "time_constraints_snapshot", "daily_progress_snapshot"],
        status="open",
        today=today,
        before_shift=before_shift,
        during_shift=during_shift,
        after_shift=after_shift,
        top_priorities=top_p,
        constraints=cons,
        risks_to_watch=risks,
        a_good_day_looks_like=good_day,
    )
    return preview.to_dict()
