from __future__ import annotations

from types import SimpleNamespace


class _Cfg:
    def __init__(self, data: dict):
        self.data = data

    def get(self, dotted: str, default=None):
        cur = self.data
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur


class _Req:
    def __init__(self, payload=None):
        self.payload = payload or {}

    def execute(self):
        return self.payload


class _Sheets:
    def values(self):
        return self

    def get(self, spreadsheetId, range=None, fields=None, valueRenderOption=None):
        if fields:
            return _Req({"sheets": [{"properties": {"sheetId": 7, "title": "TARGET"}}]})
        if range and range.endswith("!1:1"):
            return _Req({"values": [["date", "company", "description", "amount", "", "processed", "notes"]]})
        if range and "!A2:" in range:
            return _Req({"values": [["1/1/25"]]})
        return _Req({})

    def batchGet(self, spreadsheetId, ranges, valueRenderOption=None):
        return _Req({"valueRanges": [{"range": rng, "values": [["Date", "EXPENSE"]]} for rng in ranges]})

    def batchUpdate(self, spreadsheetId, body):
        return _Req({})

    def append(self, spreadsheetId, range, valueInputOption, insertDataOption, body):
        return _Req({})


class _Service:
    def spreadsheets(self):
        return _Sheets()


def _cfg() -> _Cfg:
    return _Cfg(
        {
            "google": {"service_account_json_path": "service-account.json"},
            "sheets": {
                "companies": [
                    {
                        "key": "NUGZ",
                        "workbook_url": "https://docs.google.com/spreadsheets/d/source-sheet-id/edit",
                    }
                ]
            },
            "intake": {"csv_processor": {"header_rows": 1}},
            "intake_static_dates": {
                "header_row": 1,
                "first_row": 2,
                "dates": ["1/1/25"],
            },
            "posting": {
                "sheets": {"apply": True},
                "mark_posted": True,
                "append_transactions": False,
                "source_tab_fill": {"enabled": False},
            },
        }
    )


def test_successful_post_audit_metadata_stays_per_source_row(monkeypatch):
    from services.posting import jgdtruth_poster
    from services.state.store import State

    csv_text = "\n".join(
        [
            "date,company,description,amount,unused,processed,notes",
            "2025-01-01,NUGZ,Alpha vendor,1.00,,FALSE,",
            "2025-01-01,NUGZ,Beta vendor,2.00,,FALSE,",
        ]
    )
    rules = {
        "alpha": SimpleNamespace(
            source="Alpha vendor",
            target_sheet="TARGET",
            target_header="EXPENSE",
            approved=True,
            company_id="NUGZ",
        ),
        "beta": SimpleNamespace(
            source="Beta vendor",
            target_sheet="TARGET",
            target_header="EXPENSE",
            approved=True,
            company_id="NUGZ",
        ),
    }
    recorded: list[dict] = []

    def fake_download(_sid, _service_account, *, sheet_name_override=None):
        if sheet_name_override == "BANK":
            return "date,company,description,amount,unused,processed,notes\n"
        return csv_text

    def fake_record_successful_post(**kwargs):
        recorded.append(kwargs)

    monkeypatch.setenv("KYLO_INSTANCE_ID", "NUGZ_TEST")
    monkeypatch.setattr(jgdtruth_poster, "load_config", lambda: _cfg())
    monkeypatch.setattr(jgdtruth_poster, "load_state", lambda: State())
    monkeypatch.setattr(jgdtruth_poster, "save_state", lambda _state: None)
    monkeypatch.setattr(jgdtruth_poster, "_get_service", lambda: _Service())
    monkeypatch.setattr(jgdtruth_poster, "google_api_execute", lambda req, policy=None, label="": req.execute())
    monkeypatch.setattr(jgdtruth_poster, "download_petty_cash_csv", fake_download)
    monkeypatch.setattr(jgdtruth_poster, "fetch_rules_from_jgdtruth", lambda _company: rules)
    monkeypatch.setattr(jgdtruth_poster, "record_successful_post", fake_record_successful_post)

    result = jgdtruth_poster.run("NUGZ")

    assert result["cells_written"] == 1
    assert result["rows_marked_true"] == 2
    assert [item["description"] for item in recorded] == ["Alpha vendor", "Beta vendor"]
    assert [item["amount_cents"] for item in recorded] == [100, 200]
    assert [item["row0"] for item in recorded] == [1, 2]
    assert len({item["txn_uid"] for item in recorded}) == 2
