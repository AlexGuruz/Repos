"""Optional fast answers before full orchestrator / LLM."""
from __future__ import annotations

from typing import Any

from .intent_map import resolve_intent_key
from .job_primer import load_job_primer
from .settings import get_settings
from .tools.growflow_ops import get_growflow_status
from .approvals import list_pending_approvals


def try_fast_reply(message: str) -> dict[str, Any] | None:
    """
    If Operator Desk can answer without LLM, return orchestrator-shaped dict.
    Returns None to fall through to brain.orchestrator.main.run.
    Honors OPERATOR_DESK_ENABLED / settings.enabled.
    """
    try:
        if not get_settings().enabled:
            return None
    except Exception:
        return None

    intent = resolve_intent_key(message or "")
    if intent is None:
        return None

    if intent in ("growflow_status", "retail_status"):
        primer = load_job_primer("growflow_retail")
        status = get_growflow_status()
        bits = [
            status.summary or "(no summary)",
            f"source={status.source} freshness={status.freshness}",
        ]
        if status.known_blockers:
            bits.append("blockers: " + ", ".join(status.known_blockers))
        if status.warnings:
            bits.append("warnings: " + "; ".join(status.warnings))
        if primer.ok:
            bits.append("(Job growflow_retail primed)")
        return {"reply": "\n".join(bits), "approval_request": None}

    if intent == "pending_approvals":
        pending = list_pending_approvals()
        if not pending.items:
            reply = "No pending approvals in the brain queue."
        else:
            lines = [f"- {i.approval_id}: {i.action_type} — {i.reason}" for i in pending.items[:20]]
            reply = f"{len(pending.items)} pending approval(s):\n" + "\n".join(lines)
        return {"reply": reply, "approval_request": None}

    return None
