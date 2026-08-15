from __future__ import annotations

from services.posting import jgdtruth_poster
from services.rules.jgdtruth_provider import Rule


class _Cfg:
    def __init__(self) -> None:
        self.data = {
            "sheets": {
                "companies": [
                    {
                        "key": "JGD",
                        "workbook_url": "https://docs.google.com/spreadsheets/d/target_sid/edit",
                    }
                ]
            },
            "google": {"service_account_json_path": "unused.json"},
            "intake": {
                "workbook_url": "https://docs.google.com/spreadsheets/d/intake_sid/edit",
                "csv_processor": {"header_rows": 1},
                "static_dates": ["1/1/26", "1/2/26"],
            },
            "intake_static_dates": {"header_row": 1, "first_row": 2, "dates": ["1/1/26", "1/2/26"]},
            "posting": {
                "sheets": {"apply": True},
                "mark_posted": True,
                "append_transactions": False,
                "source_tab_fill": {"enabled": False},
            },
            "runtime": {"dry_run": False},
            "matching": {"relaxed_companies": []},
            "dates": {"relaxed_companies": []},
        }

    def get(self, dotted: str, default=None):
        cur = self.data
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur


class _Req:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


class _Values:
    def get(self, **kwargs):
        return _Req(**kwargs)

    def batchGet(self, **kwargs):
        return _Req(**kwargs)

    def batchUpdate(self, **kwargs):
        return _Req(**kwargs)


class _Spreadsheets:
    def values(self):
        return _Values()

    def get(self, **kwargs):
        return _Req(**kwargs)

    def batchUpdate(self, **kwargs):
        return _Req(**kwargs)


class _Service:
    def spreadsheets(self):
        return _Spreadsheets()


def test_post_audit_records_each_source_row_when_transactions_share_target_cell(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KYLO_INSTANCE_ID", "JGD_2026")
    monkeypatch.setattr(jgdtruth_poster, "load_config", lambda: _Cfg())
    monkeypatch.setattr(jgdtruth_poster, "_get_service", lambda: _Service())
    monkeypatch.setattr(
        jgdtruth_poster,
        "fetch_rules_from_jgdtruth",
        lambda company: {
            "Alpha": Rule("Alpha", "JGD EXPENSES", "SUPPLIES", True, "JGD"),
            "Beta": Rule("Beta", "JGD EXPENSES", "SUPPLIES", True, "JGD"),
        },
    )

    def fake_download(spreadsheet_id, service_account_path, *, sheet_name_override=None, **_kwargs):
        if sheet_name_override == "BANK":
            return "date,company,description,amount,unused,processed\n"
        return (
            "date,company,description,amount,unused,processed\n"
            "2026-01-02,JGD,Alpha,10.00,,\n"
            "2026-01-02,JGD,Beta,20.00,,\n"
        )

    monkeypatch.setattr(jgdtruth_poster, "download_petty_cash_csv", fake_download)

    records: list[dict] = []

    def fake_record_successful_post(**kwargs):
        records.append(kwargs)

    monkeypatch.setattr(jgdtruth_poster, "record_successful_post", fake_record_successful_post)
    monkeypatch.setattr(jgdtruth_poster, "is_txn_flagged", lambda **_kwargs: False)

    def fake_google_api_execute(req, policy=None, label=""):
        if label == "target:tabs_meta":
            return {"sheets": [{"properties": {"sheetId": 7, "title": "JGD EXPENSES"}}]}
        if label == "batchGet:headers":
            return {"valueRanges": [{"range": "'JGD EXPENSES'!1:1", "values": [["DATE", "SUPPLIES"]]}]}
        if label == "target:date_col_read":
            return {"values": [["1/1/26"], ["1/2/26"]]}
        if label == "read:header_row":
            return {"values": [["date", "company", "description", "amount", "unused", "processed", "notes"]]}
        return {}

    monkeypatch.setattr(jgdtruth_poster, "google_api_execute", fake_google_api_execute)

    result = jgdtruth_poster.run("JGD", verify=False)

    assert result["cells_written"] == 1
    assert len(records) == 2
    assert {record["description"] for record in records} == {"Alpha", "Beta"}
    assert {record["amount_cents"] for record in records} == {1000, 2000}
    assert {record["row0"] for record in records} == {1, 2}
    assert {record["target_a1"] for record in records} == {"'JGD EXPENSES'!B3"}
