"""
Automation planner (PDR Phase 3). Builds a plan from user goal: steps, graph, connectors, risks.
Output can be turned into ProposalRecords for approval-gated execution.
"""
from __future__ import annotations

from typing import Any


def build_plan(goal: str) -> dict[str, Any]:
    """
    Produce an automation plan for the given goal.
    Returns: steps, graph (Mermaid), connectors, credentials needed, risks.
    V1: stub returns minimal structure.
    """
    _ = goal
    return {
        "steps": [],
        "graph": "flowchart TD\n  A[Goal] --> B[Not yet implemented]\n",
        "connectors": [],
        "credentials": [],
        "risks": [],
    }


def plan_to_mermaid(plan: dict[str, Any]) -> str:
    """Return Mermaid flowchart string from plan. Plan may have 'graph' key or we generate from steps."""
    return plan.get("graph") or "flowchart TD\n  A[Plan]\n"
