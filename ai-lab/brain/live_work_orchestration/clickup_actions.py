"""
ClickUp action proposals (Phase 10). Preview and queue only — no API execution.

Every proposal is ``approval_required: true`` and ``action_classification: external-side-effect``.
"""
from __future__ import annotations

import hashlib
from typing import Any

from brain.orchestrator.approval_gate import requires_approval

from brain.live_work_orchestration.clickup_queue import queue_clickup_action, queue_clarification
from brain.live_work_orchestration.clickup_routing import (
    CLICKUP_LIST_CLARIFICATIONS,
    classify_work_category,
    map_category_to_clickup_list,
    route_comment,
    route_task,
)


def _external_side_effect_meta() -> dict[str, Any]:
    return {"action_classification": "external-side-effect"}


def _approval_required_fail_closed(action: str, tool: str) -> bool:
    """Always require approval for ClickUp side effects (do not trust registry to weaken)."""
    _ = requires_approval(action, tool)
    return True


def build_clickup_task_proposal(
    work_demand: dict[str, Any],
    *,
    clickup_tool_available: bool = False,
    enqueue: bool = False,
) -> dict[str, Any]:
    title = str(work_demand.get("title") or work_demand.get("notes") or "Planner follow-up task").strip()
    routed = route_task(work_demand)
    category = str(routed.get("category") or "")
    target_list = str(routed.get("target_list") or "")
    approval_required = _approval_required_fail_closed("create", "clickup_task")

    if not clickup_tool_available:
        status = "preview-only"
        preview_reason = "tool-limited preview-only: ClickUp integration path not enabled in this runtime."
    else:
        status = "preview-only"
        preview_reason = "ClickUp writes remain approval-gated; no automatic execution in this module."

    dup_key = hashlib.sha1(f"{target_list}|{title}".encode("utf-8")).hexdigest()[:16]
    queued = None
    if enqueue:
        queued = queue_clickup_action(
            action_type="task_create",
            target_list=target_list,
            target_task_id=None,
            title=title,
            message=str(work_demand.get("notes") or ""),
            category=category,
            reason=str(work_demand.get("notes") or "work_demand"),
            source=str(work_demand.get("source") or "live_work"),
            evidence=list(work_demand.get("evidence") or []),
            approval_required=approval_required,
            status="queued",
        )
    return {
        "type": "clickup_task_proposal",
        "queue_item_id": queued.get("id") if queued else None,
        "target_list": target_list,
        "task_name": title,
        "category": category,
        "status": status,
        "preview_reason": preview_reason,
        "reason": str(work_demand.get("notes") or "work_demand"),
        "approval_required": approval_required,
        "duplicate_check_key": dup_key,
        "preview_only": True,
        **_external_side_effect_meta(),
    }


def build_clickup_comment_proposal(
    payload: dict[str, Any],
    *,
    force_clarification_list: bool = False,
    enqueue: bool = False,
) -> dict[str, Any]:
    text = str(payload.get("message") or payload.get("body") or payload.get("notes") or "").strip()
    if not text:
        text = "Clarify priority and blocking dependency for current work item."
    if force_clarification_list:
        category = classify_work_category(
            " ".join(str(payload.get(k) or "") for k in ("category", "reason", "message", "notes", "title"))
        )
        target_list = CLICKUP_LIST_CLARIFICATIONS
    else:
        routed = route_comment(payload)
        category = str(routed.get("category") or "")
        target_list = str(routed.get("target_list") or "")
    approval_required = _approval_required_fail_closed("send", "clickup_comment")
    queued = None
    if enqueue:
        queued = queue_clickup_action(
            action_type="comment",
            target_list=target_list,
            target_task_id=str(payload.get("target_task_id") or "") or None,
            title=str(payload.get("title") or "Comment"),
            message=text,
            category=category,
            reason=str(payload.get("reason") or "planner_comment"),
            source=str(payload.get("source") or "live_work"),
            evidence=list(payload.get("evidence") or []),
            approval_required=approval_required,
            status="queued",
        )
    return {
        "type": "clickup_comment_proposal",
        "queue_item_id": queued.get("id") if queued else None,
        "target_list": target_list,
        "message": text,
        "category": category,
        "reason": str(payload.get("reason") or "planner_comment"),
        "approval_required": approval_required,
        "preview_only": True,
        **_external_side_effect_meta(),
    }


def build_clickup_update_proposal(
    payload: dict[str, Any],
    *,
    enqueue: bool = False,
) -> dict[str, Any]:
    """Proposal for task field / status updates (no execution)."""
    routed = route_task(payload)
    category = str(routed.get("category") or "")
    target_list = str(routed.get("target_list") or "")
    task_id = str(payload.get("target_task_id") or payload.get("clickup_task_id") or "").strip() or None
    approval_required = _approval_required_fail_closed("update", "clickup_task_update")
    queued = None
    if enqueue and task_id:
        queued = queue_clickup_action(
            action_type="status_update",
            target_list=target_list,
            target_task_id=task_id,
            title=str(payload.get("title") or "Task update"),
            message=str(payload.get("message") or payload.get("notes") or ""),
            category=category,
            reason=str(payload.get("reason") or "planner_update"),
            source=str(payload.get("source") or "live_work"),
            evidence=list(payload.get("evidence") or []),
            approval_required=approval_required,
            status="queued",
        )
    return {
        "type": "clickup_update_proposal",
        "queue_item_id": queued.get("id") if queued else None,
        "target_list": target_list,
        "target_task_id": task_id,
        "category": category,
        "reason": str(payload.get("reason") or "planner_update"),
        "approval_required": approval_required,
        "preview_only": True,
        **_external_side_effect_meta(),
    }


def build_clickup_clarification_proposal(
    blocker_or_question: dict[str, Any],
    *,
    enqueue: bool = False,
    use_one_question_queue: bool = False,
) -> dict[str, Any]:
    """Planner clarification: routed to **Agent Clarifications**; optional local one-question queue."""
    text = str(
        blocker_or_question.get("message") or blocker_or_question.get("notes") or ""
    ).strip()
    if not text:
        text = "Clarify priority and blocking dependency for current work item."
    category = classify_work_category(
        " ".join(
            str(blocker_or_question.get(k) or "")
            for k in ("category", "reason", "message", "notes", "title")
        )
    )
    target_list = CLICKUP_LIST_CLARIFICATIONS
    approval_required = _approval_required_fail_closed("send", "clickup_comment")
    cq_item = None
    pos = 0
    if use_one_question_queue and enqueue:
        cq_item = queue_clarification(
            message=text,
            reason=str(blocker_or_question.get("reason") or "planner_clarification"),
            source=str(blocker_or_question.get("source") or "live_work"),
            evidence=list(blocker_or_question.get("evidence") or []),
            target_list=target_list,
        )
        from brain.live_work_orchestration.clickup_queue import list_clarification_items

        items = list_clarification_items()
        pos = next((i for i, x in enumerate(items, start=1) if x.get("id") == cq_item.get("id")), len(items))
    return {
        "type": "clickup_clarification_proposal",
        "clarification_queue_id": cq_item.get("id") if cq_item else None,
        "target_list": target_list,
        "message": text,
        "reason": str(blocker_or_question.get("reason") or "planner_clarification"),
        "category": category,
        "one_question_queue_position": pos,
        "approval_required": approval_required,
        "preview_only": True,
        "queue_item_id": None,
        **_external_side_effect_meta(),
    }


def build_clickup_actions_from_plan(
    plan_preview: dict[str, Any],
    snapshots: dict[str, Any],
    *,
    clickup_tool_available: bool = False,
    enqueue: bool = False,
) -> dict[str, Any]:
    wd = ((snapshots.get("work_demand_snapshot") or {}).get("data") or {}).get("demands") or []
    gaps = ((snapshots.get("planning_gaps_snapshot") or {}).get("data") or {}).get("gaps") or []
    blockers = [
        {"message": str(g.get("notes") or ""), "reason": str(g.get("gap_type") or "planning_gap"), "source": "planning_gaps"}
        for g in gaps[:3]
        if isinstance(g, dict)
    ]

    task_props = [
        build_clickup_task_proposal(w, clickup_tool_available=clickup_tool_available, enqueue=enqueue)
        for w in wd[:5]
    ]
    clar_props = [
        build_clickup_clarification_proposal(b, enqueue=enqueue, use_one_question_queue=True)
        for b in blockers[:1]
    ]

    return {
        "type": "live_work_clickup_action_batch",
        "day_plan": {
            "today": plan_preview.get("today"),
            "before_shift": plan_preview.get("before_shift"),
            "during_shift": plan_preview.get("during_shift"),
            "after_shift": plan_preview.get("after_shift"),
        },
        "clickup_tasks": task_props,
        "blockers": blockers,
        "clickup_clarifications": clar_props,
        "approval_required": True,
        **_external_side_effect_meta(),
        "no_direct_write_performed": True,
    }


def generate_clickup_action_recommendations(
    plan_preview: dict[str, Any],
    snapshots: dict[str, Any],
    *,
    clickup_tool_available: bool = False,
    enqueue: bool = False,
) -> dict[str, Any]:
    """
    Read-only recommendations: plan tasks, proposed ClickUp payloads, clarifications, pending approval.
    """
    batch = build_clickup_actions_from_plan(
        plan_preview=plan_preview,
        snapshots=snapshots,
        clickup_tool_available=clickup_tool_available,
        enqueue=enqueue,
    )
    gaps = ((snapshots.get("planning_gaps_snapshot") or {}).get("data") or {}).get("gaps") or []
    pending_clarifications = [
        {
            "message": str(g.get("notes") or g.get("gap_type") or "gap"),
            "target_list": CLICKUP_LIST_CLARIFICATIONS,
            "reason": "planning_gap",
        }
        for g in gaps[:5]
        if isinstance(g, dict)
    ]
    proposed = list(batch.get("clickup_tasks") or []) + list(batch.get("clickup_clarifications") or [])
    suggested_updates: list[dict[str, Any]] = []
    return {
        "plan": {
            "tasks": batch.get("clickup_tasks") or [],
            "day_plan": batch.get("day_plan") or {},
        },
        "clickup_actions": {
            "proposed_tasks": batch.get("clickup_tasks") or [],
            "queued_clarifications": batch.get("clickup_clarifications") or [],
            "suggested_updates": suggested_updates,
        },
        "status": "pending approval",
        "proposed_clickup_actions": proposed,
        "pending_clarifications": pending_clarifications,
        "no_execution": True,
        **{k: v for k, v in batch.items() if k in ("blockers", "type", "approval_required", "no_direct_write_performed", "action_classification")},
    }
