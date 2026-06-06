"""Tests for bank vendor cleaner LLM system-prompt injection."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from brain.bank_vendor_cleaner.llm_context import (
    BANK_VENDOR_ACTIVE_TOPIC,
    append_to_system_prompt,
    build_llm_system_addon,
    is_bank_vendor_context,
)
from brain.orchestrator.main import run


def test_is_bank_vendor_context_by_phrase():
    assert is_bank_vendor_context("what canonical label for Murphy fuel?")
    assert not is_bank_vendor_context("what is the weather today")


def test_is_bank_vendor_context_by_intent():
    assert is_bank_vendor_context("hello", intent="bank_vendor_qa")
    assert is_bank_vendor_context("run it", params={"tool_hint": "bank_vendor_cleaner_pipeline"})


def test_is_bank_vendor_context_by_active_topic():
    with patch("brain.session_state.peek_active_topic", return_value=BANK_VENDOR_ACTIVE_TOPIC):
        assert is_bank_vendor_context("explain the last run", session_id="test-session")


def test_build_llm_system_addon_includes_operating_prompt():
    addon = build_llm_system_addon(max_operating_prompt_chars=8000)
    assert "transaction-cleaning engine" in addon
    assert "Hard operating rules" in addon
    assert "Processing order for each row" in addon
    assert "Not the write path" in addon


def test_append_to_system_prompt_injects_when_relevant():
    base = "You are the Command Center assistant."
    out = append_to_system_prompt(
        base,
        "how does vendor lookup work?",
        session_id="s1",
        intent="bank_vendor_qa",
        params={},
    )
    assert out.startswith(base)
    assert "Hard operating rules" in out
    assert len(out) > len(base) + 200


def test_append_to_system_prompt_skips_unrelated():
    base = "You are the Command Center assistant."
    out = append_to_system_prompt(
        base,
        "what is the weather?",
        session_id="s1",
        intent="answer",
        params={},
    )
    assert out == base


def test_orchestrator_injects_policy_into_llm_system_message():
    captured: list[list[dict]] = []

    def fake_chat(_base_url, _model, messages, **_kwargs):
        captured.append(messages)
        return "Murphy is the canonical label."

    fake_grounded = {
        "evidence_block": "Resolved: test\nKey evidence:\n(none)",
        "proposals_suffix": "",
        "proposals": [],
        "answer_style": "direct_status",
        "routing_reason": "test",
        "stage_timings_ms": {},
        "evidence_count": 0,
        "sources_used": [],
    }

    with patch("brain.orchestrator.main.build_grounded_response", return_value=fake_grounded), \
         patch("brain.orchestrator.main.chat_completion", side_effect=fake_chat), \
         patch("brain.orchestrator.main._write_turn_trace_if_enabled"), \
         patch.dict("os.environ", {"AI_LAB_ORCH_NO_LLM": ""}, clear=False):
        result = run(
            "what canonical label should Murphy fuel get?",
            llm_base_url="http://127.0.0.1:1234/v1",
            llm_model="test-model",
            write_response_trace=False,
        )

    assert "Murphy" in result["reply"]
    assert captured
    system = captured[0][0]["content"]
    assert "Hard operating rules" in system
    assert "transaction-cleaning engine" in system
