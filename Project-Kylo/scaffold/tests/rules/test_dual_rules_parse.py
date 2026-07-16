"""Unit tests for dual-rule parsing / intake routing helpers."""
from __future__ import annotations

from services.rules.jgdtruth_provider import Rule, _parse_rules_rows


def test_parse_rules_rows_reads_pool_event_intake_columns():
    values = [
        [
            "Unique Source",
            "Target Sheet",
            "Target Header",
            "APPROVED",
            "COMPANY ID",
            "Pool",
            "Event Type",
            "Intake Tab",
            "Notes",
        ],
        ["SQUARE", "INCOME", "SQUARE", True, "", "BANK", "OPERATING", "BANK", ""],
        ["FROM BANK", "INCOME", "FROM BANK", True, "", "TRANSFER", "TRANSFER_IN", "TRANSACTIONS", ""],
        ["REG 1 DEPOSIT", "INCOME", "REG 1", True, "", "CASH", "OPERATING", "TRANSACTIONS", ""],
    ]
    rules = _parse_rules_rows(values, company_id="JGD", default_approved=False)
    assert "SQUARE" in rules
    assert rules["SQUARE"].pool == "BANK"
    assert rules["SQUARE"].event_type == "OPERATING"
    assert rules["SQUARE"].intake_tab == "BANK"
    assert rules["FROM BANK"].pool == "TRANSFER"
    assert rules["FROM BANK"].event_type == "TRANSFER_IN"
    assert rules["REG 1 DEPOSIT"].pool == "CASH"


def test_parse_rules_rows_legacy_without_extra_columns_still_works():
    values = [
        ["Unique Source", "Target sheet", "Target Header", "APPROVED", "COMPANY ID"],
        ["ATM LOAD", "JGD", "ATM LOAD", True, ""],
    ]
    rules = _parse_rules_rows(values, company_id="JGD")
    assert rules["ATM LOAD"].target_sheet == "JGD"
    assert rules["ATM LOAD"].pool is None
    assert rules["ATM LOAD"].intake_tab is None


def test_rule_dataclass_defaults_compat():
    r = Rule(source="X", target_sheet="INCOME", target_header="REG 1", approved=True)
    assert r.pool is None
    assert r.company_id is None
