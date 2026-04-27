from __future__ import annotations

from brain import session_state
from brain.execution import run
from brain.orchestrator.main import run as orchestrator_run
from brain.schemas.proposals import ProposalRecord


def test_direct_execution_run_cannot_bypass_approval_for_state_changing_tool() -> None:
    result = run("repo_full_rebuild_gate_a", {"repo_id": "ai-lab"})
    assert result.success is False
    assert result.exit_code == 3
    assert "approval policy" in result.stderr.lower()


def test_state_changing_tool_missing_metadata_fails_closed() -> None:
    result = run("brand_new_state_changer", {"foo": "bar"}, approval_context={"approved": True})
    assert result.success is False
    assert result.exit_code == 3
    assert "missing approval metadata" in result.stderr.lower()


def test_read_only_tool_still_runs_without_approval(monkeypatch) -> None:
    fake_entry = {"tool_name": "growflow_sales_today", "path": "integrations/growflow/sales_today.py", "repo": "Greg-Kylo"}

    monkeypatch.setattr("brain.execution._find_tool", lambda name: fake_entry if name == "growflow_sales_today" else None)
    monkeypatch.setattr("brain.execution._resolve_path", lambda entry: __import__("pathlib").Path(__file__))

    class _Proc:
        returncode = 0
        stdout = "ok"
        stderr = ""

    monkeypatch.setattr("brain.execution.subprocess.run", lambda *args, **kwargs: _Proc())
    result = run("growflow_sales_today", {"date": "today"})
    assert result.success is True
    assert result.exit_code == 0


def test_orchestrator_do_it_blocks_approval_required_actions() -> None:
    sid = "phase1_orch_parity"
    session_state.get(sid)
    session_state.set_pending_proposal(
        sid,
        ProposalRecord(
            action="worker_n8n_trigger",
            title="Trigger worker workflow",
            description="Trigger n8n workflow",
            tool="worker_n8n_trigger",
            args={"workflow": "wf"},
            approval_required=True,
            expires_after_turns=3,
        ),
    )
    out = orchestrator_run("do it", llm_base_url="", llm_model="", session_id=sid)
    assert "approval-gated" in out["reply"]

