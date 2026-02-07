from types import SimpleNamespace

from scaffold.tools.db_memory import InMemoryRulesDB
from scaffold.tools.importer import importer_run


class FakeSheets:
    def __init__(self, tabs):
        self._tabs = tabs
        self._last_payload = None

    def spreadsheets(self):
        return self

    def get(self, spreadsheetId, fields):
        # include also Active sheet discovery with arbitrary ids
        sheets_meta = []
        for t in self._tabs:
            sheets_meta.append({"properties": {"sheetId": t["sheetId"], "title": t["title"]}})
        sheets_meta.append({"properties": {"sheetId": 202, "title": "Active Rules – 710"}})
        return SimpleNamespace(execute=lambda: {"sheets": sheets_meta})

    def values(self):
        return self

    def batchGetByDataFilter(self, spreadsheetId, body):
        vals = []
        for t in self._tabs:
            vals.append({"valueRange": {"values": t.get("values", [])}})
        return SimpleNamespace(execute=lambda: {"valueRanges": vals})

    def batchUpdate(self, spreadsheetId, body):
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


def test_integration_two_new_one_duplicate():
    # Two new + one duplicate by same source should result in a single active projection row per source
    rows = [
        ["", "2/19/25", "coffee shop", "710", "$ 12.34", "Cash", "Food", "", "TRUE", "R1", ""],
        ["", "2/19/25", "coffee shop", "710", "$ 15.00", "Cash", "Food", "", "TRUE", "R2", ""],
        ["", "2/20/25", "bookstore", "710", "$ 9.99", "Cash", "Office", "", "TRUE", "R3", ""],
    ]
    tabs = [
        {"sheetId": 201, "title": "Pending Rules – 710", "values": _pending_values_with_headers(rows)},
    ]
    sheets = FakeSheets(tabs)
    db = InMemoryRulesDB()

    res = importer_run(sheets, db, "spread")
    assert res["touched"] == ["710"]
    # Check batch payload exists and has at least one updateCells for Active and two for Pending marks
    assert sheets._last_payload is not None
    reqs = sheets._last_payload["requests"]
    assert any(r.get("updateCells", {}).get("range", {}).get("sheetId") == 202 for r in reqs)


