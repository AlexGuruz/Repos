from __future__ import annotations

from unittest.mock import patch

import pytest

from brain import permanent_allowlist


@pytest.fixture
def allowlist_store(tmp_path):
    store_dir = tmp_path / "approval_logs"
    store_path = store_dir / "permanent_allowlist.json"
    with patch.object(permanent_allowlist, "_store_dir", store_dir), \
         patch.object(permanent_allowlist, "_store_path", store_path):
        yield store_path


def test_permanent_rule_matches_scoped_payload(allowlist_store):
    rule = permanent_allowlist.add_rule(
        "run_approved",
        {"file_path": r"C:\Repos\ai-lab\README.md", "tool_name": "doc_tool", "ignored": "x"},
        note="docs",
    )

    assert rule["id"].startswith("PAR-")
    assert permanent_allowlist.find_matching_rule(
        "run_approved",
        {"file_path": "C:/Repos/ai-lab/README.md", "tool_name": "doc_tool", "extra": "ok"},
    ) == rule
    assert permanent_allowlist.find_matching_rule(
        "run_approved",
        {"file_path": "C:/Repos/ai-lab/README.md", "tool_name": "other"},
    ) is None


def test_permanent_rule_requires_scoped_match_and_safe_action(allowlist_store):
    with pytest.raises(ValueError, match="match"):
        permanent_allowlist.add_rule("run_approved", {})

    with pytest.raises(ValueError, match="cannot"):
        permanent_allowlist.add_rule("restart_service", {"target": "backend"})


def test_brain_spec_match_payload_normalizes_approval_rows(allowlist_store):
    payload = permanent_allowlist.brain_spec_match_payload(
        {
            "action": "run_approved",
            "file_path": r"C:\Repos\ai-lab\brain\main.py",
            "detail": "Needs approval",
        }
    )

    assert payload == {
        "file_path": "C:/Repos/ai-lab/brain/main.py",
        "action_type": "run_approved",
        "reason": "Needs approval",
    }
