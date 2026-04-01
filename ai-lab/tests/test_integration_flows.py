"""
Integration-style tests for Phase 3.1 (Guru §24).

These avoid external LLM and heavy repo scans; they validate end-to-end session behavior,
conversational fallback, and proposal expiry/approval boundaries.
"""
from __future__ import annotations

from brain.orchestrator.main import run
from brain import session_state
from brain.schemas.proposals import ProposalRecord


def test_greeting_fallback_does_not_insufficient_evidence():
    out = run("hello", llm_base_url="", llm_model="", session_id="it_greet")
    assert "Ready" in out["reply"]


def test_normalize_greeting_variants():
    """Guru §24.13: normalized input (strip, lower, trailing punctuation) matches allowlist."""
    for msg in ("hi", "Hi", "  hi  ", "hi!", "hello...", "help"):
        out = run(msg, llm_base_url="", llm_model="", session_id="it_norm")
        assert out.get("approval_request") is None
        if msg.strip().lower().rstrip(".!?").strip() in ("hi", "hello"):
            assert "Ready" in out["reply"]
        elif msg.strip().lower().rstrip(".!?").strip() == "help":
            assert "help" in out["reply"].lower() or "can help" in out["reply"].lower()


def test_insufficient_evidence_returns_conversational_reply():
    """Guru §24.13: no-evidence turn returns fixed conversational reply, not generic [Orchestrator] fallback."""
    # Vague question with no session evidence should hit insufficient_evidence override
    out = run(
        "what did the last scan find?",
        llm_base_url="",
        llm_model="",
        session_id="it_no_evidence_never_used",
    )
    assert "reply" in out
    reply = out["reply"]
    # Must NOT be the generic fallback
    assert "[Orchestrator] Intent:" not in reply or "I don't have any evidence" in reply
    # Should be the hard no-evidence reply
    assert "I don't have any evidence" in reply or "Nothing to go on" in reply or "evidence" in reply.lower()


def test_proposal_expiry_clears_pending():
    sid = "it_expiry"
    session_state.get(sid)  # init
    session_state.set_pending_proposal(sid, ProposalRecord(
        action="repo_search",
        title="Search repos",
        description="Search repos",
        approval_required=False,
        expires_after_turns=1,
        args={"query": "x"},
    ))
    # Advance turns: one user message increments turn
    run("something else", llm_base_url="", llm_model="", session_id=sid)
    run("another turn", llm_base_url="", llm_model="", session_id=sid)
    assert session_state.get_pending_proposal(sid) is None


def test_do_it_without_pending_is_safe():
    out = run("do it", llm_base_url="", llm_model="", session_id="it_no_pending")
    assert "No pending action" in out["reply"]

