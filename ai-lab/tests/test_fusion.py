"""Unit tests for evidence fusion (PDR Phase 2.75)."""
import pytest
from brain.orchestrator.evidence_fusion import fuse_evidence
from brain.schemas.evidence import LoadedEvidence, EvidenceItem
from brain.schemas.routing import RoutingDecision, LocalTarget


def test_fuse_sets_answer_style():
    decision = RoutingDecision(
        intent="answer",
        needs_local=True,
        answer_style_hint="summary_from_artifact",
    )
    evidence = LoadedEvidence(
        local_evidence=[EvidenceItem(source_type="markdown_summary", content="Scan: 3 repos.")],
    )
    fused = fuse_evidence(message="what did the scan say", intent="answer", decision=decision, evidence=evidence)
    assert fused.recommended_answer_style == "summary_from_artifact"
    assert len(fused.key_evidence) >= 1
    assert fused.constraints or len(fused.key_evidence) >= 1


def test_fuse_insufficient_evidence():
    decision = RoutingDecision(intent="answer", needs_local=True)
    evidence = LoadedEvidence(local_evidence=[], sufficient=False)
    fused = fuse_evidence(message="what did the scan say", intent="answer", decision=decision, evidence=evidence)
    assert fused.resolved_question
    assert fused.recommended_answer_style in ("insufficient_evidence", "direct_status") or not fused.key_evidence


def test_fuse_time_context_avoids_insufficient():
    """Time-only answer turns must not be classified as insufficient_evidence."""
    decision = RoutingDecision(intent="answer", needs_local=False, answer_style_hint="direct_status")
    evidence = LoadedEvidence(
        local_evidence=[],
        web_evidence=[],
        time_context={"current_datetime": "2026-01-01T12:00:00", "timezone": "UTC"},
    )
    fused = fuse_evidence(message="what time is it", intent="answer", decision=decision, evidence=evidence)
    assert fused.recommended_answer_style == "direct_status"


def test_fuse_hardware_control_candidate():
    """Guru §25: hardware_status + responsive message + process_top adds set_process_priority candidate."""
    decision = RoutingDecision(intent="hardware_status", needs_local=True, answer_style_hint="direct_status")
    evidence = LoadedEvidence(
        local_evidence=[
            EvidenceItem(
                source_type="hardware_snapshot",
                content="CPU 50%",
                metadata={
                    "cpu": {
                        "process_top": [
                            {"pid": 12345, "name": "ollama"},
                            {"pid": 67890, "name": "cursor"},
                        ],
                    },
                },
            ),
        ],
    )
    fused = fuse_evidence(
        message="keep the main rig responsive while ai runs",
        intent="hardware_status",
        decision=decision,
        evidence=evidence,
    )
    candidates = [c for c in fused.proposal_candidates if c.get("action") == "set_process_priority"]
    assert len(candidates) == 1
    assert candidates[0].get("args", {}).get("pid") == 12345
    assert candidates[0].get("approval_required") is True
