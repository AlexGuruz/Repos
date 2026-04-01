"""Unit tests for proposal engine and ProposalRecord (PDR Phase 2.75)."""
import pytest
from brain.schemas.proposals import ProposalRecord
from brain.orchestrator.proposal_engine import build_proposals
from brain.schemas.evidence import FusedContext, EvidenceItem


def test_proposal_record_to_dict():
    p = ProposalRecord(
        action="repo_search",
        title="Search repos",
        description="Find script",
        tool="repo_search",
        args={"query": "growflow"},
        approval_required=False,
        expires_after_turns=3,
    )
    d = p.to_dict()
    assert d["action"] == "repo_search"
    assert d["args"]["query"] == "growflow"
    assert "created_at" in d


def test_proposal_record_from_dict():
    d = {"action": "patch_registry", "title": "Update registry", "args": {"target": "/path"}}
    p = ProposalRecord.from_dict(d)
    assert p.action == "patch_registry"
    assert p.args.get("target") == "/path"


def test_build_proposals_from_candidates():
    fused = FusedContext(
        resolved_question="What next?",
        proposal_candidates=[
            {"action": "repo_search", "title": "Search", "approval_required": False},
        ],
    )
    proposals = build_proposals(fused)
    assert len(proposals) >= 1
    assert proposals[0].action == "repo_search"


def test_build_proposals_default_scan():
    fused = FusedContext(
        resolved_question="Summarize scan",
        key_evidence=[EvidenceItem(source_type="markdown_summary", content="Findings")],
    )
    proposals = build_proposals(fused)
    assert len(proposals) >= 1
    assert any(p.action == "show_scan_results" or p.action == "repo_search" for p in proposals)
