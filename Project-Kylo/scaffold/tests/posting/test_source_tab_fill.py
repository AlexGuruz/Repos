"""Unit tests for JGD target cell background fill (BANK vs TRANSACTIONS)."""

from __future__ import annotations

import json

import pytest

from services.posting.jgdtruth_poster import (
    _build_sheet_title_to_id,
    _color_for_source_tabs,
    _parse_target_cell_a1,
    _rgb_triple_from_cfg,
    apply_source_tab_fill_colors,
)


def test_parse_target_cell_a1_quoted_tab():
    assert _parse_target_cell_a1("'JGD EXPENSES'!B20") == ("JGD EXPENSES", 20, 1)


def test_parse_target_cell_a1_escaped_quote_in_tab():
    assert _parse_target_cell_a1("'JGD''SHEET'!AA100") == ("JGD'SHEET", 100, 26)


def test_parse_target_cell_a1_simple_tab():
    assert _parse_target_cell_a1("BANK!A1") == ("BANK", 1, 0)


def test_parse_target_cell_a1_invalid():
    assert _parse_target_cell_a1("") is None
    assert _parse_target_cell_a1("norange") is None


def test_color_for_source_tabs():
    tx = {"red": 1.0, "green": 0.0, "blue": 0.0}
    bank = {"red": 0.0, "green": 1.0, "blue": 0.0}
    mixed = {"red": 0.0, "green": 0.0, "blue": 1.0}
    assert _color_for_source_tabs({"TRANSACTIONS"}, tx, bank, mixed) == tx
    assert _color_for_source_tabs({"BANK"}, tx, bank, mixed) == bank
    assert _color_for_source_tabs({"BANK", "TRANSACTIONS"}, tx, bank, mixed) == mixed
    assert _color_for_source_tabs({"CREDIT CARDS"}, tx, bank, mixed) == mixed


def test_rgb_triple_from_cfg_defaults():
    block: dict = {}
    d = _rgb_triple_from_cfg(block, "missing", (0.1, 0.2, 0.3))
    assert d == {"red": 0.1, "green": 0.2, "blue": 0.3}


def test_build_sheet_title_to_id():
    meta = {
        "sheets": [
            {"properties": {"sheetId": 7, "title": "JGD EXPENSES"}},
            {"properties": {"sheetId": 9, "title": "BANK"}},
        ]
    }
    m = _build_sheet_title_to_id(meta)
    assert m["jgd expenses"] == 7
    assert m["bank"] == 9


def test_apply_source_tab_fill_colors_disabled(monkeypatch):
    bodies: list = []

    def fake_execute(req, policy=None, label=""):
        raw = getattr(req, "body", None)
        if isinstance(raw, str):
            bodies.append(json.loads(raw))
        else:
            bodies.append(raw)
        return {}

    monkeypatch.setattr("services.posting.jgdtruth_poster.google_api_execute", fake_execute)
    n = apply_source_tab_fill_colors(
        object(),
        "sid",
        {"posting": {"source_tab_fill": {"enabled": False}}},
        {"'T'!A1"},
        {"'T'!A1": {"TRANSACTIONS"}},
        {"t": 1},
    )
    assert n == 0
    assert bodies == []


def test_apply_source_tab_fill_colors_builds_repeat_cell(monkeypatch):
    monkeypatch.delenv("KYLO_SOURCE_TAB_FILL", raising=False)
    bodies: list = []

    class _Svc:
        def spreadsheets(self):
            return self

        def batchUpdate(self, spreadsheetId, body):
            bodies.append(body)
            self._sid = spreadsheetId

            class _R:
                def execute(self_inner):
                    return {}

            return _R()

    cfg = {
        "posting": {
            "source_tab_fill": {
                "enabled": True,
                "transactions_rgb": [1.0, 0.0, 0.0],
                "bank_rgb": [0.0, 1.0, 0.0],
                "mixed_rgb": [0.0, 0.0, 1.0],
            }
        }
    }
    n = apply_source_tab_fill_colors(
        _Svc(),
        "sid",
        cfg,
        {"'JGD EXPENSES'!B2"},
        {"'JGD EXPENSES'!B2": {"BANK"}},
        {"jgd expenses": 3},
    )
    assert n == 1
    assert len(bodies) == 1
    req = bodies[0]["requests"][0]["repeatCell"]
    assert req["fields"] == "userEnteredFormat.backgroundColor"
    assert req["range"]["sheetId"] == 3
    assert req["range"]["startRowIndex"] == 1
    assert req["range"]["startColumnIndex"] == 1
    assert req["cell"]["userEnteredFormat"]["backgroundColor"]["green"] == 1.0


def test_env_kylo_source_tab_fill_off(monkeypatch):
    monkeypatch.setenv("KYLO_SOURCE_TAB_FILL", "0")
    bodies: list = []

    def fake_execute(req, policy=None, label=""):
        bodies.append(1)
        return {}

    monkeypatch.setattr("services.posting.jgdtruth_poster.google_api_execute", fake_execute)
    n = apply_source_tab_fill_colors(
        object(),
        "sid",
        {"posting": {"source_tab_fill": {"enabled": True}}},
        {"'T'!A1"},
        {"'T'!A1": {"BANK"}},
        {"t": 1},
    )
    assert n == 0
    assert bodies == []
