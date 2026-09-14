from __future__ import annotations

from typing import Any, Dict, List

from services.posting import jgdtruth_poster as poster
from services.rules.jgdtruth_provider import Rule
from services.state.store import State


class _Config:
    def __init__(self) -> None:
        self.data: Dict[str, Any] = {
            "google": {"service_account_json_path": "unused.json"},
            "sheets": {
                "companies": [
                    {
                        "key": "NUGZ",
                        "workbook_url": "https://docs.google.com/spreadsheets/d/default-target/edit",
                    }
                ]
            },
            "year_workbooks_active": [2026],
            "year_workbooks": {
                "2026": {
                    "intake_workbook_url": "https://docs.google.com/spreadsheets/d/intake-sid/edit",
                    "output_workbook_url": "https://docs.google.com/spreadsheets/d/target-sid/edit",
                }
            },
            "intake": {"extra_tabs": []},
            "intake_static_dates": {"header_row": 19, "first_row": 20, "dates": ["1/1/26"]},
            "posting": {
                "sheets": {"apply": True},
                "mark_posted": True,
                "append_transactions": False,
                "source_tab_fill": {"enabled": False},
            },
            "matching": {"relaxed_companies": []},
            "dates": {"relaxed_companies": []},
        }

    def get(self, dotted_key: str, default: Any = None) -> Any:
        cur: Any = self.data
        for part in dotted_key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur


class _Req:
    def __init__(self, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)


class _Service:
    def spreadsheets(self) -> "_Service":
        return self

    def values(self) -> "_Service":
        return self

    def get(self, **kwargs: Any) -> _Req:
        return _Req(method="get", **kwargs)

    def batchGet(self, **kwargs: Any) -> _Req:
        return _Req(method="batchGet", **kwargs)

    def batchUpdate(self, **kwargs: Any) -> _Req:
        return _Req(method="batchUpdate", **kwargs)

    def append(self, **kwargs: Any) -> _Req:
        return _Req(method="append", **kwargs)


class _Processor:
    def __init__(self, _csv_content: str, *, source_tab: str, source_spreadsheet_id: str, **_kwargs: Any) -> None:
        self.source_tab = source_tab
        self.source_spreadsheet_id = source_spreadsheet_id

    def parse_transactions(self) -> List[Dict[str, Any]]:
        if self.source_tab != "TRANSACTIONS":
            return []
        return [
            {
                "company_id": "NUGZ",
                "description": "FIRST VENDOR",
                "amount_cents": 1000,
                "posted_date": "2026-01-01",
                "row_index_0based": 20,
                "txn_uid": "txn-1",
                "posted_flag": False,
            },
            {
                "company_id": "NUGZ",
                "description": "SECOND VENDOR",
                "amount_cents": 2000,
                "posted_date": "2026-01-01",
                "row_index_0based": 21,
                "txn_uid": "txn-2",
                "posted_flag": False,
            },
        ]


def _install_poster_fakes(monkeypatch, *, fail_mark: bool = False) -> List[Dict[str, Any]]:
    audit_calls: List[Dict[str, Any]] = []

    def fake_execute(req: _Req, policy: Any = None, label: str = "") -> Dict[str, Any]:
        if label == "target:tabs_meta":
            return {"sheets": [{"properties": {"sheetId": 7, "title": "NUGZ COG"}}]}
        if label == "batchGet:headers":
            return {"valueRanges": [{"range": "'NUGZ COG'!19:19", "values": [["Date", "Supplies"]]}]}
        if label == "target:date_col_read":
            return {"values": [["1/1/26"]]}
        if label == "read:header_row":
            return {"values": [["Date", "Description", "Amount", "Company", "Unused", "Posted", "Notes"]]}
        if label == "source:mark_posted_batch" and fail_mark:
            raise RuntimeError("simulated source mark failure")
        return {}

    def fake_rules(_company: str) -> Dict[str, Rule]:
        return {
            "FIRST VENDOR": Rule("FIRST VENDOR", "NUGZ COG", "Supplies", True, "NUGZ"),
            "SECOND VENDOR": Rule("SECOND VENDOR", "NUGZ COG", "Supplies", True, "NUGZ"),
        }

    def fake_record_successful_post(**kwargs: Any) -> None:
        audit_calls.append(kwargs)

    monkeypatch.setattr(poster, "load_config", lambda: _Config())
    monkeypatch.setattr(poster, "load_state", lambda: State())
    monkeypatch.setattr(poster, "save_state", lambda _state: None)
    monkeypatch.setattr(poster, "_get_service", lambda: _Service())
    monkeypatch.setattr(poster, "download_petty_cash_csv", lambda *_args, **_kwargs: "unused")
    monkeypatch.setattr("services.intake.csv_processor.PettyCashCSVProcessor", _Processor)
    monkeypatch.setattr(poster, "fetch_rules_from_jgdtruth", fake_rules)
    monkeypatch.setattr(poster, "google_api_execute", fake_execute)
    monkeypatch.setattr(poster, "HttpError", RuntimeError)
    monkeypatch.setattr(poster, "format_post_note", lambda amount, tab, header, date_key, flagged=False: f"note {amount}")
    monkeypatch.setattr(poster, "is_txn_flagged", lambda **_kwargs: False)
    monkeypatch.setattr(poster, "record_successful_post", fake_record_successful_post)
    monkeypatch.setenv("KYLO_INSTANCE_ID", "NUGZ_2026")
    return audit_calls


def test_post_audit_preserves_each_source_transaction_metadata(monkeypatch):
    audit_calls = _install_poster_fakes(monkeypatch)

    result = poster.run("NUGZ")

    assert result["error"] is False
    assert result["rows_marked_true"] == 2
    assert [call["txn_uid"] for call in audit_calls] == ["txn-1", "txn-2"]
    assert [call["description"] for call in audit_calls] == ["FIRST VENDOR", "SECOND VENDOR"]
    assert [call["amount_cents"] for call in audit_calls] == [1000, 2000]


def test_source_mark_failure_is_returned_as_watcher_error(monkeypatch):
    _install_poster_fakes(monkeypatch, fail_mark=True)

    result = poster.run("NUGZ")

    assert result["source_mark_failed"] is True
    assert result["error"] is True
    assert result["rows_marked_true"] == 0
