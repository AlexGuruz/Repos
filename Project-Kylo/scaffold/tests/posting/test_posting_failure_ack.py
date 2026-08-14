import json


class _Cfg:
    def __init__(self):
        self.data = {
            "sheets": {
                "companies": [
                    {"key": "JGD", "workbook_url": "target-spreadsheet"},
                ]
            },
            "google": {"service_account_json_path": "unused.json"},
            "posting": {
                "sheets": {"apply": True},
                "mark_posted": True,
                "source_tab_fill": {"enabled": False},
                "append_transactions": False,
            },
            "runtime": {"dry_run": False},
            "intake": {
                "csv_processor": {"header_rows": 1},
                "static_dates": ["1/1/26"],
                "extra_tabs": [],
            },
            "intake_static_dates": {"header_row": 1, "first_row": 2},
            "matching": {"relaxed_companies": []},
            "dates": {"relaxed_companies": []},
            "year_workbooks": {},
            "year_workbooks_active": [],
        }

    def get(self, dotted, default=None):
        cur = self.data
        for part in str(dotted).split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur


class _FakeService:
    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, **_kwargs):
        return object()

    def batchGet(self, **_kwargs):
        return object()

    def batchUpdate(self, **_kwargs):
        return object()

    def append(self, **_kwargs):
        return object()


class _FakeHttpError(Exception):
    def __init__(self, content):
        super().__init__(content)
        self.content = content
        self.status_code = 400


def test_posting_reports_failed_target_range(monkeypatch, tmp_path):
    from services.posting import jgdtruth_poster as poster
    from services.rules.jgdtruth_provider import Rule
    from services.intake import csv_processor

    cfg = _Cfg()
    monkeypatch.setenv("KYLO_STATE_PATH", str(tmp_path / "posting_state.json"))
    monkeypatch.delenv("KYLO_READ_ONLY", raising=False)
    monkeypatch.delenv("KYLO_SHEETS_DRY_RUN", raising=False)
    monkeypatch.setattr(poster, "load_config", lambda: cfg)
    monkeypatch.setattr(csv_processor, "load_config", lambda: cfg)
    monkeypatch.setattr(poster, "_get_service", lambda: _FakeService())
    monkeypatch.setattr(poster, "HttpError", _FakeHttpError)
    monkeypatch.setattr(
        poster,
        "fetch_rules_from_jgdtruth",
        lambda company: {"STORE": Rule("STORE", "TARGET", "TOTAL", True, "JGD")},
    )

    def fake_download(_sid, _service_account, sheet_name_override=None):
        header = "Date,Company,Description,Amount,Other,Processed,Notes\n"
        if str(sheet_name_override).upper() == "BANK":
            return header
        return header + "2026-01-01,JGD,STORE,12.34,,FALSE,\n"

    monkeypatch.setattr(poster, "download_petty_cash_csv", fake_download)

    def fake_execute(_req, policy=None, label=""):
        if label == "target:tabs_meta":
            return {"sheets": [{"properties": {"sheetId": 1, "title": "TARGET"}}]}
        if label == "batchGet:headers":
            return {"valueRanges": [{"range": "TARGET!1:1", "values": [["Date", "TOTAL"]]}]}
        if label == "target:date_col_read":
            return {"values": [["1/1/26"]]}
        if label == "target:batchUpdate_values":
            raise _FakeHttpError("Invalid data[0]: protected cell")
        return {}

    monkeypatch.setattr(poster, "google_api_execute", fake_execute)

    result = poster.run("JGD")

    assert result["error"] is True
    assert result["failed_range_count"] == 1
    assert result["failed_ranges"] == ["TARGET!B2"]
    assert result["rows_marked_true"] == 0


def test_watcher_does_not_ack_failed_posting_summary(monkeypatch, tmp_path):
    from kylo import watcher_runtime
    from services.posting import jgdtruth_poster

    watch_state = tmp_path / "watch_state.json"
    old_state = {
        "seen": {"JGD": {"rules": "old-rules", "intake": "old-intake"}},
        "acked": {"JGD": {"rules": "old-rules", "intake": "old-intake"}},
    }
    watch_state.write_text(json.dumps(old_state), encoding="utf-8")

    cfg = _Cfg()
    monkeypatch.setattr(watcher_runtime, "WATCH_STATE_PATH", str(watch_state))
    monkeypatch.setattr(watcher_runtime, "load_config", lambda: cfg)
    monkeypatch.setattr(watcher_runtime, "is_audit_mode", lambda _cfg: False)
    monkeypatch.setattr(watcher_runtime, "run_audit_tick", lambda *args, **kwargs: {})
    monkeypatch.setattr(watcher_runtime, "rules_checksum", lambda _cid: "new-rules")
    monkeypatch.setattr(watcher_runtime, "intake_checksum", lambda _cfg, _cid: "new-intake")
    monkeypatch.setattr(
        jgdtruth_poster,
        "run",
        lambda _cid, rules_changed=False: {"failed_range_count": 1, "failed_ranges": ["TARGET!B2"]},
    )

    result = watcher_runtime.tick_once(["JGD"])
    saved = json.loads(watch_state.read_text(encoding="utf-8"))

    assert result["posting_attempted"] is True
    assert saved["seen"]["JGD"] == {"rules": "new-rules", "intake": "new-intake"}
    assert saved["acked"]["JGD"] == {"rules": "old-rules", "intake": "old-intake"}
    assert saved["circuit_breaker"]["consecutive_failures"] == 1
