from __future__ import annotations

from types import SimpleNamespace

from services.posting import jgdtruth_poster as poster
from services.state.store import State


class _Cfg:
    def __init__(self, data):
        self.data = data

    def get(self, key, default=None):
        cur = self.data
        for part in str(key).split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur


class _Request:
    def __init__(self, op: str, **kwargs):
        self.op = op
        self.kwargs = kwargs


class _Values:
    def get(self, **kwargs):
        return _Request("values.get", **kwargs)

    def batchGet(self, **kwargs):
        return _Request("values.batchGet", **kwargs)

    def batchUpdate(self, **kwargs):
        return _Request("values.batchUpdate", **kwargs)


class _Spreadsheets:
    def __init__(self):
        self._values = _Values()

    def values(self):
        return self._values

    def get(self, **kwargs):
        return _Request("spreadsheets.get", **kwargs)


class _Service:
    def __init__(self):
        self._spreadsheets = _Spreadsheets()

    def spreadsheets(self):
        return self._spreadsheets


class _Processor:
    def __init__(self, *_args, source_tab: str = "", **_kwargs):
        self.source_tab = source_tab

    def parse_transactions(self):
        if self.source_tab != "TRANSACTIONS":
            return iter([])
        return iter(
            [
                {
                    "txn_uid": "txn-alpha",
                    "company_id": "JGD",
                    "posted_date": "2026-01-01",
                    "amount_cents": 100,
                    "description": "Alpha",
                    "row_index_0based": 1,
                    "posted_flag": False,
                },
                {
                    "txn_uid": "txn-beta",
                    "company_id": "JGD",
                    "posted_date": "2026-01-02",
                    "amount_cents": 200,
                    "description": "Beta",
                    "row_index_0based": 2,
                    "posted_flag": False,
                },
            ]
        )


def test_posting_audit_records_use_each_source_transaction(monkeypatch):
    cfg = _Cfg(
        {
            "google": {"service_account_json_path": "sa.json"},
            "sheets": {
                "companies": [
                    {
                        "key": "JGD",
                        "workbook_url": "https://docs.google.com/spreadsheets/d/source-sheet/edit",
                    }
                ]
            },
            "year_workbooks": {
                "2026": {
                    "intake_workbook_url": "https://docs.google.com/spreadsheets/d/source-sheet/edit",
                    "output_workbook_url": "https://docs.google.com/spreadsheets/d/target-sheet/edit",
                }
            },
            "intake": {"csv_processor": {"header_rows": 1}, "extra_tabs": []},
            "intake_static_dates": {"header_row": 1, "first_row": 20},
            "posting": {"sheets": {"apply": True}, "mark_posted": True},
            "runtime": {"dry_run": False},
            "matching": {"relaxed_companies": []},
        }
    )
    state = State()
    captured_flag_checks = []
    captured_posts = []

    monkeypatch.setenv("KYLO_INSTANCE_ID", "KYLO_TEST")
    monkeypatch.delenv("KYLO_SHEETS_DRY_RUN", raising=False)
    monkeypatch.delenv("KYLO_READ_ONLY", raising=False)
    monkeypatch.delenv("KYLO_ACTIVE_YEARS", raising=False)
    monkeypatch.setattr(poster, "load_config", lambda: cfg)
    monkeypatch.setattr(poster, "load_state", lambda: state)
    monkeypatch.setattr(poster, "save_state", lambda _state: None)
    monkeypatch.setattr(poster, "_get_service", lambda: _Service())
    monkeypatch.setattr(poster, "download_petty_cash_csv", lambda *_args, **_kwargs: "csv")
    monkeypatch.setattr("services.intake.csv_processor.PettyCashCSVProcessor", _Processor)
    monkeypatch.setattr(
        poster,
        "fetch_rules_from_jgdtruth",
        lambda _company: {
            "Alpha": SimpleNamespace(
                source="Alpha",
                approved=True,
                target_sheet="TARGET",
                target_header="Food",
                company_id="JGD",
            ),
            "Beta": SimpleNamespace(
                source="Beta",
                approved=True,
                target_sheet="TARGET",
                target_header="Food",
                company_id="JGD",
            ),
        },
    )

    def fake_execute(req, policy=None, label=""):
        if label == "target:tabs_meta":
            return {"sheets": [{"properties": {"sheetId": 7, "title": "TARGET"}}]}
        if label == "batchGet:headers":
            return {"valueRanges": [{"range": "TARGET!1:1", "values": [["Date", "Food"]]}]}
        if label == "target:date_col_read":
            return {"values": [["1/1/26"], ["1/2/26"]]}
        if label == "read:header_row":
            return {"values": [["Date", "Company", "Description", "Amount", "", "Processed", "Notes"]]}
        if getattr(req, "op", "") == "values.batchUpdate":
            return {}
        raise AssertionError(f"unexpected execute label={label} op={getattr(req, 'op', None)}")

    def fake_is_flagged(**kwargs):
        captured_flag_checks.append(kwargs)
        return False

    def fake_record_post(**kwargs):
        captured_posts.append(kwargs)

    monkeypatch.setattr(poster, "google_api_execute", fake_execute)
    monkeypatch.setattr(poster, "is_txn_flagged", fake_is_flagged)
    monkeypatch.setattr(poster, "record_successful_post", fake_record_post)

    result = poster.run("JGD", verify=False)

    assert result["rows_marked_true"] == 2
    assert [(p["txn_uid"], p["posted_date"], p["description"]) for p in captured_posts] == [
        ("txn-alpha", "2026-01-01", "Alpha"),
        ("txn-beta", "2026-01-02", "Beta"),
    ]
    assert [(c["posted_date"], c["description"]) for c in captured_flag_checks] == [
        ("2026-01-01", "Alpha"),
        ("2026-01-02", "Beta"),
    ]
