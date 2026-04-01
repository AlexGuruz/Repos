"""
Session state for Local Assistant V1: working memory per chat session.
Tracks last tool action, last artifacts, last failure, recent entities.
PDR Phase 2.75: turn_counter, user_timezone, typed pending_proposal, expiry.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Union

# In-memory store: session_id -> state dict. No persistence in V1.
_SESSIONS: dict[str, dict[str, Any]] = {}

# Schema (see Guru.md §19, PDR §2):
# active_project, active_topic, last_tool_action, last_artifacts, last_failure, recent_entities,
# approval_mode, pending_proposal, turn_counter, user_timezone, last_web_lookup, last_routing_decision


def _now() -> str:
    # UTC, timezone-aware (avoid datetime.utcnow() deprecation)
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(session_id: str) -> dict[str, Any]:
    """Return current session state. Creates empty session if missing."""
    if session_id not in _SESSIONS:
        # Try to load persisted state first (Phase 3.1)
        try:
            from brain.session_store import load_session
            loaded = load_session(session_id)
        except Exception:
            loaded = None

        _SESSIONS[session_id] = loaded or {
            "active_project": "ai-lab",
            "active_topic": None,
            "last_tool_action": None,
            "last_artifacts": [],
            "last_failure": None,
            "recent_entities": [],
            "approval_mode": "strict",
            "pending_proposal": None,
            "last_web_lookup": None,
            "last_routing_decision": None,
            "turn_counter": 0,
            "user_timezone": "America/Chicago",
        }
    return _SESSIONS[session_id]


def _persist(session_id: str) -> None:
    """Best-effort persistence for Phase 3.1."""
    try:
        from brain.session_store import save_session
        save_session(session_id, get(session_id))
    except Exception:
        pass


def get_active_topic(session_id: str) -> str | None:
    """Return current active topic if any."""
    return get(session_id).get("active_topic")


def update_active_topic(session_id: str, topic: str | None) -> None:
    """Set or clear the current conversation topic (e.g. growflow_sales_issue, repo_scan_analysis)."""
    get(session_id)["active_topic"] = topic
    _persist(session_id)


def set_pending_proposal(
    session_id: str,
    proposal: Union[dict[str, Any], "ProposalRecord"],
) -> None:
    """Store a proposed action (ProposalRecord or dict). Sets created_at and creation_turn for expiry."""
    from brain.schemas.proposals import ProposalRecord
    state = get(session_id)
    if isinstance(proposal, ProposalRecord):
        d = proposal.to_dict()
    else:
        d = dict(proposal)
        if "created_at" not in d:
            d["created_at"] = _now()
    d["creation_turn"] = state.get("turn_counter", 0)
    state["pending_proposal"] = d
    _persist(session_id)


def clear_pending_proposal(session_id: str) -> None:
    """Clear pending proposal after approval/deny or when superseded."""
    get(session_id)["pending_proposal"] = None
    _persist(session_id)


def get_pending_proposal(session_id: str) -> dict[str, Any] | None:
    """Return current pending proposal if any (dict with action, args, created_at, expires_after_turns, etc.)."""
    return get(session_id).get("pending_proposal")


def get_turn_counter(session_id: str) -> int:
    """Return current turn count for the session."""
    return get(session_id).get("turn_counter", 0)


def increment_turn(session_id: str) -> int:
    """Increment turn counter; return new value."""
    state = get(session_id)
    state["turn_counter"] = state.get("turn_counter", 0) + 1
    _persist(session_id)
    return state["turn_counter"]


def is_proposal_expired(session_id: str) -> bool:
    """True if pending_proposal exists and has exceeded expires_after_turns since created_at."""
    prop = get_pending_proposal(session_id)
    if not prop:
        return False
    created = prop.get("created_at")
    expires_after = prop.get("expires_after_turns", 3)
    if not created:
        return False
    try:
        # created_at is turn index when we stored it; we don't have turn at storage time, so use turn_counter as proxy
        # Simpler: treat created_at as timestamp and expires_after_turns as number of turns. We need turn when created.
        # Store creation_turn when setting proposal:
        creation_turn = prop.get("creation_turn")
        if creation_turn is None:
            return False
        current = get_turn_counter(session_id)
        return (current - creation_turn) > expires_after
    except Exception:
        return False


def get_user_timezone(session_id: str) -> str:
    """Return user timezone (e.g. America/Chicago). Default America/Chicago."""
    return get(session_id).get("user_timezone") or "America/Chicago"


def set_user_timezone(session_id: str, tz: str) -> None:
    """Set user timezone for time context."""
    get(session_id)["user_timezone"] = tz
    _persist(session_id)


def set_last_web_lookup(session_id: str, query: str, results: dict[str, Any]) -> None:
    """Store last web lookup for session (query + results summary)."""
    get(session_id)["last_web_lookup"] = {"query": query, "results": results, "timestamp": _now()}
    _persist(session_id)


def get_last_web_lookup(session_id: str) -> dict[str, Any] | None:
    """Return last web lookup record if any."""
    return get(session_id).get("last_web_lookup")


def set_last_routing_decision(session_id: str, decision: dict[str, Any]) -> None:
    """Store last routing decision for debugging/trace."""
    get(session_id)["last_routing_decision"] = {**decision, "timestamp": _now()}
    _persist(session_id)


def get_last_routing_decision(session_id: str) -> dict[str, Any] | None:
    """Return last routing decision if any."""
    return get(session_id).get("last_routing_decision")


def update_after_tool(
    session_id: str,
    tool_name: str,
    status: str,
    artifacts: list[dict] | None = None,
    summary: dict | None = None,
    failure_reason: str | None = None,
    failure_path: str | None = None,
) -> None:
    """Update session after a tool run. Call with status 'ok' or 'failed'."""
    state = get(session_id)
    state["last_tool_action"] = {
        "name": tool_name,
        "status": status,
        "timestamp": _now(),
    }
    if artifacts:
        state["last_artifacts"] = [
            {**a, "timestamp": a.get("timestamp") or _now()}
            for a in artifacts
        ]
    elif status == "ok" and not state.get("last_artifacts"):
        state["last_artifacts"] = []
    if status == "failed":
        state["last_failure"] = {
            "intent": tool_name,
            "reason": failure_reason or "unknown",
            "path": failure_path,
        }
    else:
        state["last_failure"] = None
    # Keep recent_entities bounded
    for tag in [tool_name, "repo scan" if "scan" in tool_name else None]:
        if tag and tag not in state["recent_entities"]:
            state["recent_entities"] = [tag] + state["recent_entities"][:9]
    _persist(session_id)


def get_last_scan_artifact(session_id: str) -> dict | None:
    """Return the most recent repo_scan artifact entry, or None."""
    state = get(session_id)
    for a in state.get("last_artifacts") or []:
        if a.get("type") == "repo_scan":
            return a
    return None


def get_last_failure(session_id: str) -> dict | None:
    """Return last failure record if any."""
    return get(session_id).get("last_failure")
