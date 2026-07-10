"""
Shared approval enforcement guard used across execution lanes.

Phase 1 goal: one policy decision model for orchestrator, execution, and supervisor paths.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from brain.orchestrator.approval_gate import requires_approval
from brain.tool_registry import get_tool_metadata


@dataclass
class ApprovalDecision:
    allowed: bool
    requires_approval: bool
    classification: str
    reason: str


_READ_ONLY_SIDE_EFFECTS = {"read_only", "read", "none"}
_SYSTEM_CONTROL_MARKERS = ("restart", "priority", "affinity", "registry", "workflow", "n8n")


def _classify_action(action: str, meta: dict[str, Any] | None) -> str:
    side_effects = str((meta or {}).get("side_effects") or "").strip().lower()
    risk_level = str((meta or {}).get("risk_level") or "").strip().lower()
    a = (action or "").strip().lower()
    if a in {"run_script", "run_approved", "submit_approval", "write_sheet"}:
        return "external-side-effect"
    if side_effects in _READ_ONLY_SIDE_EFFECTS:
        return "read-only"
    if any(m in a for m in _SYSTEM_CONTROL_MARKERS):
        return "system-control"
    if "write" in side_effects or "modif" in side_effects or "delete" in side_effects:
        return "modifies-files-or-state"
    if "trigger" in side_effects or "api" in side_effects or "external" in side_effects:
        return "external-side-effect"
    if risk_level in {"high", "critical"}:
        return "system-control"
    if risk_level == "medium":
        return "external-side-effect"
    return "read-only"


def evaluate_action(
    *,
    action: str,
    tool_name: str | None = None,
    approved: bool = False,
    fail_closed_on_missing_metadata: bool = False,
) -> ApprovalDecision:
    key = (tool_name or action or "").strip()
    meta = get_tool_metadata(key) if key else None
    needs_approval = requires_approval(action, tool_name)
    classification = _classify_action(action or key, meta)

    if fail_closed_on_missing_metadata and (classification != "read-only"):
        if not meta or "approval_required" not in meta or "side_effects" not in meta:
            return ApprovalDecision(
                allowed=False,
                requires_approval=True,
                classification=classification,
                reason=f"missing approval metadata for state-changing action '{key or action}'",
            )

    if needs_approval and not approved:
        return ApprovalDecision(
            allowed=False,
            requires_approval=True,
            classification=classification,
            reason=f"approval required for '{key or action}'",
        )
    return ApprovalDecision(
        allowed=True,
        requires_approval=needs_approval,
        classification=classification,
        reason="allowed",
    )

