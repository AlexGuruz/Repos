"""
Answer strategy layer (Guru §21). Chooses how the assistant should respond.
"""
from __future__ import annotations

from brain.schemas.evidence import FusedContext


def choose_answer_style(fused: FusedContext) -> str:
    """
    Return strategy tag: direct_status, failure_explanation, summary_from_artifact,
    local_plus_web_comparison, proposal_after_analysis, approval_confirmation, insufficient_evidence.
    """
    if fused.recommended_answer_style == "insufficient_evidence":
        return "insufficient_evidence"
    if fused.recommended_answer_style:
        return fused.recommended_answer_style
    if not fused.key_evidence and not fused.secondary_evidence:
        if fused.time_context:
            return "direct_status"
        return "insufficient_evidence"
    if any(e.source_type == "failure_record" for e in fused.key_evidence):
        return "failure_explanation"
    if any(e.source_type in ("markdown_summary", "json_artifact") for e in fused.key_evidence):
        return "summary_from_artifact"
    web_items = [e for e in fused.key_evidence + fused.secondary_evidence if e.source_type == "web"]
    local_items = [e for e in fused.key_evidence + fused.secondary_evidence if e.source_type != "web"]
    if web_items and local_items:
        return "local_plus_web_comparison"
    return "direct_status"
