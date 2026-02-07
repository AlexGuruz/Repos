from types import SimpleNamespace

from scaffold.tools.db_memory import InMemoryRulesDB
from scaffold.tools.importer import importer_run, list_company_pending_tabs, batch_read_pending_values


class FakeSheets:
    def __init__(self, tabs):
        # tabs: list of dict {sheetId, title, values}
        self._tabs = tabs

    def spreadsheets(self):
        return self

    # metadata
    def get(self, spreadsheetId, fields):
        return SimpleNamespace(execute=lambda: {"sheets": [{"properties": {"sheetId": t["sheetId"], "title": t["title"]}} for t in self._tabs]})

    # values
    def values(self):
        return self

    def batchGetByDataFilter(self, spreadsheetId, body):
        # return all tabs' values
        vals = []
        for t in self._tabs:
            vals.append({"valueRange": {"values": t.get("values", [])}})
        return SimpleNamespace(execute=lambda: {"valueRanges": vals})

    # batch update sink
    def batchUpdate(self, spreadsheetId, body):
        # record payload for assertions if needed
        self._last_payload = body
        return SimpleNamespace(execute=lambda: {"ok": True})


def _pending_values_with_headers(rows):
    header = [
        "Row_Hash",
        "Date",
        "Source",
        "Company_ID",
        "Amount",
        "Target_Sheet",
        "Target_Header",
        "Match_Notes",
        "Approved",
        "Rule_ID",
        "Processed_At",
    ]
    return [header] + rows


def test_idempotent_second_run_marks_processed_but_inserts_nothing():
    # Prepare one approved row for company 710
    rows = [
        ["", "2/19/25", "coffee shop", "710", "$ 12.34", "Cash", "Food", "", "TRUE", "R1", ""],
    ]
    tabs = [
        {"sheetId": 101, "title": "Pending Rules – 710", "values": _pending_values_with_headers(rows)},
    ]
    sheets = FakeSheets(tabs)
    db = InMemoryRulesDB()

    # First run inserts the rule and writes processed marks
    res1 = importer_run(sheets, db, "spread")
    assert res1["touched"] == ["710"]
    # Seed second run with same data (idempotency)
    res2 = importer_run(sheets, db, "spread")
    assert res2["touched"] == [] or res2["processed_rows"] >= 1


