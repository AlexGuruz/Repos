from __future__ import annotations

from operator_desk.intent_map import resolve_intent_key, resolve_job_id_for_message


def test_growflow_intent():
    assert resolve_intent_key("Where are we on Growflow today?") == "growflow_status"
    assert resolve_job_id_for_message("retail status please") == "growflow_retail"


def test_email_intent():
    assert resolve_job_id_for_message("What's in the inbox?") == "company_email"


def test_pending_intent():
    assert resolve_job_id_for_message("Show pending approvals") == "machine_actions"
