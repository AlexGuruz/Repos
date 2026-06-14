from __future__ import annotations

import pytest

from core.ai_lab import ensure_ai_lab_root_on_path

ensure_ai_lab_root_on_path()

from brain import permanent_allowlist as allowlist  # noqa: E402


def test_permanent_rule_matches_exact_scoped_payload(tmp_path, monkeypatch):
    monkeypatch.setattr(allowlist, "_RULES_PATH", tmp_path / "permanent_allowlist.json")

    rule = allowlist.add_rule(
        "write_sheet",
        {"file_path": "sheets/daily.csv", "reason": "daily posting"},
        source_approval_id="APR-123",
    )

    assert rule["id"].startswith("PAR-")
    assert allowlist.find_matching_rule(
        "write_sheet",
        {"file_path": "sheets/daily.csv", "reason": "daily posting", "ignored": "x"},
    ) == rule
    assert allowlist.find_matching_rule(
        "write_sheet",
        {"file_path": "sheets/other.csv", "reason": "daily posting"},
    ) is None


def test_permanent_rule_rejects_broad_or_never_permanent_rules(tmp_path, monkeypatch):
    monkeypatch.setattr(allowlist, "_RULES_PATH", tmp_path / "permanent_allowlist.json")

    with pytest.raises(ValueError, match="scoped"):
        allowlist.add_rule("write_sheet", {"reason": "daily posting"})

    with pytest.raises(ValueError, match="cannot be permanently allowlisted"):
        allowlist.add_rule("restart_service", {"target": "command-center"})
