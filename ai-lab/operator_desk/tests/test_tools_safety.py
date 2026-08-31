from __future__ import annotations

from operator_desk.errors import ACTION_NOT_ALLOWLISTED, OperatorError
from operator_desk.approvals import submit_tool_proposal
from operator_desk.tools.growflow_ops import get_growflow_status
from operator_desk.tools.email_ops import redact_for_telemetry


def test_growflow_snapshot(tmp_snapshot):
    result = get_growflow_status()
    assert result.ok is True
    assert result.source == "prepared_snapshot"
    assert "Test snapshot" in result.summary


def test_no_raw_shell_args():
    try:
        submit_tool_proposal(
            "bank_vendor_lookup_worker",
            {"command": "rm -rf /"},
            reason="test",
        )
        assert False, "expected OperatorError"
    except OperatorError as exc:
        assert exc.code == ACTION_NOT_ALLOWLISTED


def test_unknown_tool_blocked():
    try:
        submit_tool_proposal("not_a_real_tool_zzz", {}, reason="test")
        assert False, "expected OperatorError"
    except OperatorError as exc:
        assert exc.code == ACTION_NOT_ALLOWLISTED


def test_email_redaction():
    out = redact_for_telemetry({"body": "secret", "account_id": "nugzdispo"})
    assert out["body"] == "[redacted]"
    assert out["account_id"] == "nugzdispo"
