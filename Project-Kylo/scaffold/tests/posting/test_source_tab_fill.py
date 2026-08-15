"""Unit tests for JGD target cell background fill (BANK vs TRANSACTIONS)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
import services.intake.csv_processor as csv_processor
import services.posting.jgdtruth_poster as poster

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


class _Cfg:
    def __init__(self, data):
        self.data = data

    def get(self, dotted_key, default=None):
        cur = self.data
        for part in str(dotted_key).split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur


class _Req:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _FakeValues:
    def __init__(self, calls):
        self.calls = calls

    def get(self, **kwargs):
        return _Req(kind="values_get", **kwargs)

    def batchGet(self, **kwargs):
        return _Req(kind="values_batch_get", **kwargs)

    def batchUpdate(self, **kwargs):
        self.calls.append(("values_batch_update", kwargs))
        return _Req(kind="values_batch_update", **kwargs)

    def append(self, **kwargs):
        self.calls.append(("values_append", kwargs))
        return _Req(kind="values_append", **kwargs)


class _FakeSheets:
    def __init__(self, calls):
        self.calls = calls

    def values(self):
        return _FakeValues(self.calls)

    def get(self, **kwargs):
        return _Req(kind="sheets_get", **kwargs)

    def batchUpdate(self, **kwargs):
        self.calls.append(("sheets_batch_update", kwargs))
        return _Req(kind="sheets_batch_update", **kwargs)


class _FakeService:
    def __init__(self):
        self.calls = []

    def spreadsheets(self):
        return _FakeSheets(self.calls)


def test_post_audit_metadata_stays_per_source_row_for_aggregated_target_cell(monkeypatch, tmp_path):
    cfg = _Cfg(
        {
            "runtime": {"dry_run": False},
            "sheets": {
                "companies": [
                    {
                        "key": "JGD",
                        "workbook_url": "https://docs.google.com/spreadsheets/d/target_sid/edit",
                    }
                ]
            },
            "intake": {
                "workbook_url": "https://docs.google.com/spreadsheets/d/source_sid/edit",
                "csv_processor": {"header_rows": 1},
                "extra_tabs": [],
            },
            "intake_static_dates": {"header_row": 1, "first_row": 20},
            "posting": {
                "sheets": {"apply": True},
                "mark_posted": True,
                "append_transactions": False,
                "source_tab_fill": {"enabled": False},
            },
            "matching": {"relaxed_companies": []},
            "dates": {"relaxed_companies": []},
        }
    )
    service = _FakeService()
    captured_posts = []
    flagged_checks = []

    monkeypatch.setenv("KYLO_INSTANCE_ID", "JGD_TEST")
    monkeypatch.setenv("KYLO_STATE_PATH", str(tmp_path / "posting_state.json"))
    monkeypatch.setattr(poster, "load_config", lambda: cfg)
    monkeypatch.setattr(csv_processor, "load_config", lambda: cfg)
    monkeypatch.setattr(poster, "_get_service", lambda: service)
    monkeypatch.setattr(
        poster,
        "fetch_rules_from_jgdtruth",
        lambda company: {
            "Snack": SimpleNamespace(
                source="Snack",
                target_sheet="JGD EXPENSES",
                target_header="Food",
                approved=True,
                company_id="JGD",
            ),
            "Drink": SimpleNamespace(
                source="Drink",
                target_sheet="JGD EXPENSES",
                target_header="Food",
                approved=True,
                company_id="JGD",
            ),
        },
    )

    def fake_download(spreadsheet_id, service_account, sheet_name_override=None):
        if sheet_name_override == "TRANSACTIONS":
            return "\n".join(
                [
                    "Date,Company,Description,Amount,Other,Processed,Notes",
                    "2026-06-01,JGD,Snack,1.00,,FALSE,",
                    "2026-06-01,JGD,Drink,2.00,,FALSE,",
                ]
            )
        raise RuntimeError("tab missing")

    def fake_execute(req, policy=None, label=""):
        if label == "target:tabs_meta":
            return {"sheets": [{"properties": {"sheetId": 7, "title": "JGD EXPENSES"}}]}
        if label == "batchGet:headers":
            return {"valueRanges": [{"range": "'JGD EXPENSES'!1:1", "values": [["Date", "Food"]]}]}
        if label == "target:date_col_read":
            return {"values": [["6/1/26"]]}
        if label == "read:header_row":
            return {"values": [["Date", "Company", "Description", "Amount", "Other", "Processed", "Notes"]]}
        return {}

    def fake_is_flagged(**kwargs):
        flagged_checks.append(kwargs)
        return kwargs["description"] == "Snack"

    def fake_record_successful_post(**kwargs):
        captured_posts.append(kwargs)

    monkeypatch.setattr(poster, "download_petty_cash_csv", fake_download)
    monkeypatch.setattr(poster, "google_api_execute", fake_execute)
    monkeypatch.setattr(poster, "is_txn_flagged", fake_is_flagged)
    monkeypatch.setattr(poster, "record_successful_post", fake_record_successful_post)

    result = poster.run("JGD")

    assert result["cells_written"] == 1
    assert result["rows_marked_true"] == 2
    assert [(p["description"], p["amount_cents"], p["row0"], p["flagged"]) for p in captured_posts] == [
        ("Snack", 100, 1, True),
        ("Drink", 200, 2, False),
    ]
    assert [(c["description"], c["amount_cents"]) for c in flagged_checks] == [
        ("Snack", 100),
        ("Drink", 200),
    ]
