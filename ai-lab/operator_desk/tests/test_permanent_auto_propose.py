from __future__ import annotations

from operator_desk.approvals import clear_scripts_cache, submit_tool_proposal
from brain.permanent_allowlist import add_rule, delete_rule, find_matching_rule


def test_permanent_rule_auto_executes_matching_propose(monkeypatch, tmp_path):
    clear_scripts_cache()
    # Isolate permanent store
    import brain.permanent_allowlist as pa

    state = tmp_path / "permanent_approvals.json"
    monkeypatch.setattr(pa, "_STATE_PATH", state)

    calls = {}

    def fake_run(tool_name, args, timeout=300, approval_context=None):
        calls["tool"] = tool_name
        calls["args"] = args
        calls["ctx"] = approval_context

        class R:
            success = True
            stdout = '{"ok":true}'
            stderr = ""
            exit_code = 0

        return R()

    monkeypatch.setattr("brain.execution.run", fake_run)

    rule = add_rule(
        "operator_desk_tool",
        {
            "action_type": "operator_desk_tool",
            "file_path": "operator_desk",
            "tool_name": "cc_investor_demo_ping",
            "reason": "QUAL_ALWAYS_UNIT",
        },
        note="unit",
    )
    assert find_matching_rule(
        "operator_desk_tool",
        {
            "action_type": "operator_desk_tool",
            "file_path": "operator_desk",
            "tool_name": "cc_investor_demo_ping",
            "reason": "QUAL_ALWAYS_UNIT",
        },
    )

    # submit uses real queue; ensure scripts allowlist includes tool
    out = submit_tool_proposal(
        "cc_investor_demo_ping",
        {},
        reason="QUAL_ALWAYS_UNIT",
    )
    assert out.approval_required is False
    assert out.auto_permanent is True
    assert out.permanent_rule_id == rule["id"]
    assert out.status == "auto_approved"
    assert calls.get("tool") == "cc_investor_demo_ping"
    delete_rule(rule["id"])
