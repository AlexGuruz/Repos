from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.common.rules_workbook import (  # noqa: E402
    get_rules_management_spreadsheet_id,
    spreadsheet_id_from_url,
)


def test_spreadsheet_id_from_rules_management_url() -> None:
    assert (
        spreadsheet_id_from_url("https://docs.google.com/spreadsheets/d/abc_DEF-123/edit#gid=0")
        == "abc_DEF-123"
    )


def test_rules_management_id_prefers_env(monkeypatch) -> None:
    monkeypatch.setenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "env-sheet")
    cfg = {"rules": {"management_spreadsheet_id": "cfg-sheet"}}

    assert get_rules_management_spreadsheet_id(cfg) == "env-sheet"


def test_rules_management_id_uses_config_url(monkeypatch) -> None:
    monkeypatch.delenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", raising=False)
    cfg = {"rules": {"management_workbook_url": "https://docs.google.com/spreadsheets/d/cfg-sheet/edit"}}

    assert get_rules_management_spreadsheet_id(cfg) == "cfg-sheet"
