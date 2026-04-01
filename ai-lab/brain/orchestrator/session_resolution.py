"""
Session resolution (Guru §21). Resolve references (that, it, the scan, do it) to session context.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REFERENCE_TRIGGERS = (
    "that", "it", "this", "those results", "the scan", "the failure", "the script",
    "do it", "fix it", "the output", "the report",
)


@dataclass
class SessionResolution:
    resolved_reference: str | None = None
    resolved_artifact: dict[str, Any] | None = None
    resolved_failure: dict[str, Any] | None = None
    resolved_proposal: dict[str, Any] | None = None
    active_topic: str | None = None
    confidence: float = 0.0


def resolve_session_references(message: str, session: dict[str, Any]) -> SessionResolution:
    """
    Resolve references in the message to session context.
    Priority: pending_proposal, active_topic, last_failure, last_artifacts, last_tool_action.
    """
    msg = (message or "").strip().lower()
    out = SessionResolution(
        active_topic=session.get("active_topic"),
    )
    if not msg:
        return out
    # "do it" / "fix it" -> pending proposal
    if msg.rstrip(".!?") in ("do it", "fix it", "yes", "go ahead", "do that", "approve", "ok", "sure"):
        prop = session.get("pending_proposal")
        if prop:
            out.resolved_proposal = prop
            out.resolved_reference = "pending_proposal"
            out.confidence = 0.95
            return out
    # "that scan", "the scan", "what did that tell you", "scan results"
    if any(x in msg for x in ("scan", "that tell", "results", "report", "output", "findings")):
        artifacts = session.get("last_artifacts") or []
        for a in artifacts:
            if a.get("type") == "repo_scan":
                out.resolved_artifact = a
                out.resolved_reference = "last_scan_artifact"
                out.confidence = 0.9
                return out
    # "why did that fail", "the failure"
    if "fail" in msg or "failure" in msg or "broken" in msg:
        failure = session.get("last_failure")
        if failure:
            out.resolved_failure = failure
            out.resolved_reference = "last_failure"
            out.confidence = 0.9
            return out
    # Generic "that" / "it" -> prefer last artifact or failure
    if any(x in msg for x in ("that", "it")) and out.confidence == 0:
        failure = session.get("last_failure")
        artifacts = session.get("last_artifacts") or []
        if failure:
            out.resolved_failure = failure
            out.resolved_reference = "last_failure"
            out.confidence = 0.7
        elif artifacts:
            out.resolved_artifact = artifacts[0] if artifacts else None
            out.resolved_reference = "last_artifact"
            out.confidence = 0.6
    return out
