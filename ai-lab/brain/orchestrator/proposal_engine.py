"""
Proposal engine (Guru §21). Produces 2–4 grounded next actions from FusedContext.
Uses tool_registry when available for description, approval_required, risk_level (Guru §24.14).
"""
from __future__ import annotations

from brain.schemas.evidence import FusedContext
from brain.schemas.proposals import ProposalRecord


def _tool_metadata(action: str):
    try:
        from brain.tool_registry import get_tool_metadata
        return get_tool_metadata(action) or {}
    except Exception:
        return {}


def build_proposals(fused: FusedContext) -> list[ProposalRecord]:
    """
    Build 2–4 concrete proposals from fused evidence. Read-only auto-safe; writes approval-gated.
    """
    out: list[ProposalRecord] = []
    # From fusion candidates; enrich with tool_registry when present
    for c in fused.proposal_candidates[:4]:
        action = c.get("action", "unknown")
        meta = _tool_metadata(action)
        title = c.get("title") or meta.get("description", "")[:60] or action.replace("_", " ").title()
        desc = c.get("description") or meta.get("description") or c.get("title") or title
        approval = c.get("approval_required") if "approval_required" in c else meta.get("approval_required", True)
        if meta.get("risk_level"):
            desc = (desc or "") + f" (Risk: {meta['risk_level']})"
        out.append(ProposalRecord(
            action=action,
            title=title,
            description=desc,
            tool=c.get("tool") or action,
            args=c.get("args", {}),
            approval_required=approval,
        ))
    # Defaults when we have scan/failure context
    if not out and fused.key_evidence:
        out.append(ProposalRecord(
            action="show_scan_results",
            title="Show scan results",
            description="View the latest repo scan summary.",
            approval_required=False,
        ))
        out.append(ProposalRecord(
            action="repo_search",
            title="Search repos",
            description="Search for a script or file by name.",
            tool="repo_search",
            approval_required=False,
        ))
    if fused.active_topic and "failure" in (fused.active_topic or ""):
        out.append(ProposalRecord(
            action="repo_search",
            title="Find missing script in repos",
            description="Search repos for the script that failed.",
            tool="repo_search",
            args={"query": "script"},
            approval_required=False,
        ))
    return out[:4]
