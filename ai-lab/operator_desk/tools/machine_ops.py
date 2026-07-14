"""Machine pending + proposal wrappers."""
from __future__ import annotations

from typing import Any

from ..approvals import list_pending_approvals, submit_tool_proposal
from ..models import ApprovalSubmissionResult, MachinePendingResult


def list_pending() -> MachinePendingResult:
    return list_pending_approvals()


def propose_allowlisted_action(
    tool_name: str,
    args: dict[str, Any] | None,
    *,
    reason: str,
    risk_level: str = "high",
) -> ApprovalSubmissionResult:
    return submit_tool_proposal(
        tool_name,
        args,
        reason=reason,
        risk_level=risk_level,
        action_type="operator_desk_machine",
        file_path="operator_desk/machine",
    )
