"""
Evidence fusion (Guru §21). Turns loaded evidence into a compact FusedContext for reasoning.
"""
from __future__ import annotations

from brain.schemas.routing import RoutingDecision
from brain.schemas.evidence import LoadedEvidence, FusedContext, EvidenceItem


def fuse_evidence(
    *,
    message: str,
    intent: str,
    decision: RoutingDecision,
    evidence: LoadedEvidence,
) -> FusedContext:
    """
    Build FusedContext: key_evidence, secondary_evidence, constraints, recommended_answer_style, proposal_candidates.
    """
    key_evidence: list[EvidenceItem] = []
    secondary_evidence: list[EvidenceItem] = []
    constraints: list[str] = ["Do not invent findings beyond the provided evidence."]
    proposal_candidates: list[dict] = []

    # Promote most relevant local evidence to key (ops/hardware/failure are first-class context)
    key_types = (
        "markdown_summary",
        "artifact",
        "json_artifact",
        "weather_forecast",
        "ops_registry",
        "hardware_snapshot",
        "failure_record",
        "config",
    )
    for item in evidence.local_evidence:
        if item.source_type in key_types and item.content:
            key_evidence.append(item)
        else:
            secondary_evidence.append(item)
    for item in evidence.web_evidence[:3]:
        (key_evidence if len(key_evidence) < 2 else secondary_evidence).append(item)

    # Resolved question
    resolved_question = message.strip() or "User request"
    if evidence.session_context.get("active_topic"):
        resolved_question = f"[Topic: {evidence.session_context['active_topic']}] {resolved_question}"

    # Answer style from decision
    style = decision.answer_style_hint or "direct_status"
    if not evidence.local_evidence and not evidence.web_evidence and intent == "answer":
        # Time-only turns (e.g. "what time is it") still have usable context — do not force insufficient_evidence
        if evidence.time_context:
            style = "direct_status"
        else:
            style = "insufficient_evidence"

    # Proposal candidates from structured failure diagnosis (Guru §24.14)
    for item in evidence.local_evidence:
        if item.source_type == "failure_record" and item.metadata and item.metadata.get("failure_analysis"):
            fa = item.metadata["failure_analysis"]
            actions_added = set()
            for action in (fa.get("suggested_actions") or [])[:5]:
                if action == "search_repos" and "repo_search" not in actions_added:
                    proposal_candidates.append({"action": "repo_search", "title": "Search repos for script or file", "approval_required": False})
                    actions_added.add("repo_search")
                elif action == "inspect_registry" and "ops_overview" not in actions_added:
                    proposal_candidates.append({"action": "ops_overview", "title": "Inspect registry / ops overview", "approval_required": False})
                    actions_added.add("ops_overview")
                elif action == "check_worker_tunnel" and "worker_health" not in actions_added:
                    proposal_candidates.append({"action": "worker_health", "title": "Check worker tunnel and health", "approval_required": False})
                    actions_added.add("worker_health")
                elif action not in actions_added:
                    proposal_candidates.append({"action": action, "title": action.replace("_", " ").title(), "approval_required": False})
                    actions_added.add(action)
            break
    # Default proposal candidates when diagnosis/summary style and no failure-based ones yet
    if style in ("summary_from_artifact", "proposal_after_analysis") and evidence.local_evidence:
        if not proposal_candidates:
            proposal_candidates = [
                {"action": "search_repos", "title": "Search repos for script or file", "approval_required": False},
                {"action": "show_scan_results", "title": "Show scan results", "approval_required": False},
            ]
        if evidence.session_context.get("last_failure"):
            failure = evidence.session_context["last_failure"]
            if "growflow" in str(failure.get("intent", "")).lower() and not any(p.get("action") == "repo_search" for p in proposal_candidates):
                proposal_candidates.append({
                    "action": "repo_search",
                    "title": "Search for GrowFlow sales script",
                    "approval_required": False,
                })

    # Hardware control candidates (Guru §25): when we have hardware evidence and user wants responsiveness
    msg_lower = (message or "").lower()
    if intent == "hardware_status" and any(w in msg_lower for w in ("responsive", "lower priority", "pin", "headroom", "lag", "slow", "keep ")):
        for item in evidence.local_evidence:
            if item.source_type == "hardware_snapshot" and item.metadata:
                cpu = item.metadata.get("cpu") or {}
                process_top = cpu.get("process_top") or []
                if process_top:
                    top = process_top[0]
                    pid = top.get("pid")
                    name = (top.get("name") or "process").strip() or f"pid {pid}"
                    if pid is not None:
                        proposal_candidates.insert(0, {
                            "action": "set_process_priority",
                            "title": f"Lower priority of {name} (pid {pid})",
                            "description": f"Set process {pid} to lower CPU priority so the main rig stays responsive.",
                            "approval_required": True,
                            "args": {"pid": pid, "nice": 10},
                        })
                    break

    return FusedContext(
        resolved_question=resolved_question,
        active_topic=evidence.session_context.get("active_topic"),
        key_evidence=key_evidence,
        secondary_evidence=secondary_evidence,
        time_context=evidence.time_context,
        constraints=constraints,
        recommended_answer_style=style,
        proposal_candidates=proposal_candidates,
    )
