from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace


class FakeConfig:
    def __init__(self) -> None:
        self.data = {
            "runtime": {"dry_run": False},
            "posting": {"sheets": {"apply": True}, "mark_posted": True},
            "sheets": {
                "companies": [
                    {
                        "key": "JGD",
                        "workbook_url": "https://docs.google.com/spreadsheets/d/target-book/edit",
                        "tabs": {"intake": "TRANSACTIONS", "output": "Target"},
                    }
                ]
            },
            "intake": {"csv_processor": {"header_rows": 1}, "extra_tabs": []},
            "intake_static_dates": {"header_row": 1, "first_row": 2},
            "matching": {"relaxed_companies": []},
            "dates": {"relaxed_companies": []},
            "google": {"service_account_json_path": "/tmp/sa.json"},
        }

    def get(self, dotted_key: str, default=None):
        cur = self.data
        for part in dotted_key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur


class FakeService:
    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, **kwargs):
        return {"op": "get", **kwargs}

    def batchGet(self, **kwargs):
        return {"op": "batchGet", **kwargs}

    def batchUpdate(self, **kwargs):
        return {"op": "batchUpdate", **kwargs}


def _install_import_stubs(monkeypatch):
    poster = types.ModuleType("services.sheets.poster")
    poster._extract_spreadsheet_id = lambda value: str(value).split("/spreadsheets/d/")[1].split("/")[0] if "/spreadsheets/d/" in str(value) else str(value)
    poster._get_service = lambda: FakeService()
    monkeypatch.setitem(sys.modules, "services.sheets.poster", poster)

    rules_provider = types.ModuleType("services.rules.jgdtruth_provider")
    rules_provider.fetch_rules_from_jgdtruth = lambda company: {}
    monkeypatch.setitem(sys.modules, "services.rules.jgdtruth_provider", rules_provider)

    csv_downloader = types.ModuleType("services.intake.csv_downloader")
    csv_downloader.download_petty_cash_csv = lambda *args, **kwargs: ""
    monkeypatch.setitem(sys.modules, "services.intake.csv_downloader", csv_downloader)


def _load_poster(monkeypatch):
    _install_import_stubs(monkeypatch)
    sys.modules.pop("services.posting.jgdtruth_poster", None)
    return importlib.import_module("services.posting.jgdtruth_poster")


def _patch_common_runtime(monkeypatch, mod, *, fail_target_write: bool = False):
    cfg = FakeConfig()
    monkeypatch.setattr(mod, "load_config", lambda: cfg)

    import services.intake.csv_processor as csv_processor

    monkeypatch.setattr(csv_processor, "load_config", lambda: cfg)

    csv_content = "\n".join(
        [
            "Date,Company,Description,Amount,Processed,Notes",
            "2026-01-01,JGD,First vendor,10.00,,",
            "2026-01-01,JGD,Second vendor,20.00,,",
        ]
    )

    def fake_download(_sid, _sa, *, sheet_name_override=None):
        if sheet_name_override == "TRANSACTIONS":
            return csv_content
        raise RuntimeError("missing tab")

    monkeypatch.setattr(mod, "download_petty_cash_csv", fake_download)

    rules = {
        "First vendor": SimpleNamespace(
            source="First vendor",
            target_sheet="Target",
            target_header="Utilities",
            approved=True,
            company_id="JGD",
        ),
        "Second vendor": SimpleNamespace(
            source="Second vendor",
            target_sheet="Target",
            target_header="Utilities",
            approved=True,
            company_id="JGD",
        ),
    }
    monkeypatch.setattr(mod, "fetch_rules_from_jgdtruth", lambda _company: rules)

    from services.state.store import State

    monkeypatch.setattr(mod, "load_state", lambda: State())
    monkeypatch.setattr(mod, "save_state", lambda _state: None)
    monkeypatch.setattr(mod, "_get_service", lambda: FakeService())

    class FakeHttpError(Exception):
        def __init__(self, content: str) -> None:
            super().__init__(content)
            self.content = content
            self.status_code = 400

    monkeypatch.setattr(mod, "HttpError", FakeHttpError)

    def fake_execute(_request, *, label):
        if label == "target:tabs_meta":
            return {"sheets": [{"properties": {"sheetId": 123, "title": "Target"}}]}
        if label == "batchGet:headers":
            return {"valueRanges": [{"range": "Target!1:1", "values": [["Date", "Utilities"]]}]}
        if label == "target:date_col_read":
            return {"values": [["1/1/26"]]}
        if label == "target:batchUpdate_values" and fail_target_write:
            raise FakeHttpError("Invalid data[0]: protected cell")
        return {}

    monkeypatch.setattr(mod, "google_api_execute", fake_execute)
    return cfg


def test_successful_post_records_each_source_row_metadata(monkeypatch):
    mod = _load_poster(monkeypatch)
    _patch_common_runtime(monkeypatch, mod)
    monkeypatch.setenv("KYLO_INSTANCE_ID", "JGD_2026")

    flagged_calls = []
    post_calls = []

    def fake_is_txn_flagged(**kwargs):
        flagged_calls.append(kwargs)
        return False

    def fake_record_successful_post(**kwargs):
        post_calls.append(kwargs)

    monkeypatch.setattr(mod, "is_txn_flagged", fake_is_txn_flagged)
    monkeypatch.setattr(mod, "record_successful_post", fake_record_successful_post)

    result = mod.run("JGD")

    assert result["error"] is False
    assert [call["description"] for call in flagged_calls] == ["First vendor", "Second vendor"]
    assert [call["description"] for call in post_calls] == ["First vendor", "Second vendor"]
    assert [call["amount_cents"] for call in post_calls] == [1000, 2000]


def test_target_write_failure_returns_error_for_watcher_ack(monkeypatch):
    mod = _load_poster(monkeypatch)
    _patch_common_runtime(monkeypatch, mod, fail_target_write=True)

    result = mod.run("JGD")

    assert result["error"] is True
    assert result["failed_target_range_count"] > 0
