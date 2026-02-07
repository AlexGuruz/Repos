import os
from services.sheets.poster import build_batch_update


def test_build_batch_update_wraps_requests():
    changes = [
        {"updateCells": {"range": {"sheetId": 1}, "rows": [], "fields": "userEnteredValue"}},
        {"setDataValidation": {"range": {"sheetId": 1}, "rule": {"condition": {"type": "ONE_OF_LIST", "values": [{"userEnteredValue": "A"}]}}}},
    ]
    body = build_batch_update(changes)
    assert list(body.keys()) == ["requests"]
    assert body["requests"] == changes

from services.sheets.poster import SheetsPoster


def test_build_and_post_defaults():
    # Ensure dry-run mode for tests
    original = os.environ.get("KYLO_SHEETS_DRY_RUN")
    os.environ["KYLO_SHEETS_DRY_RUN"] = "true"
    try:
        ops = [{"updateCells": {"range": {"sheetId": 1}, "fields": "userEnteredValue", "rows": []}}]
        poster = SheetsPoster()
        body = poster.build_batch_update("sheet-123", ops)
        assert body == {"spreadsheetId": "sheet-123", "requests": ops}

        res = poster.post("sheet-123", ops)
        assert res["dry_run"] is True
        assert res["body"] == body
    finally:
        if original is None:
            os.environ.pop("KYLO_SHEETS_DRY_RUN", None)
        else:
            os.environ["KYLO_SHEETS_DRY_RUN"] = original


def test_single_batch_body_for_multiple_tabs():
    # Ensure dry-run mode for tests
    original = os.environ.get("KYLO_SHEETS_DRY_RUN")
    os.environ["KYLO_SHEETS_DRY_RUN"] = "true"
    try:
        ops = [
            {"updateCells": {"range": {"sheetId": 1}, "fields": "userEnteredValue", "rows": []}},
            {"updateCells": {"range": {"sheetId": 2}, "fields": "userEnteredValue", "rows": []}},
            {"setDataValidation": {"range": {"sheetId": 2}, "rule": {"condition": {"type": "NUMBER_GREATER", "values": [{"userEnteredValue": "0"}]}}}},
        ]
        poster = SheetsPoster()
        res = poster.post("sheet-xyz", ops)
        assert res["dry_run"] is True
        body = res["body"]
        assert body["spreadsheetId"] == "sheet-xyz"
        # All operations must be in a single batchUpdate body
        assert isinstance(body["requests"], list)
        assert len(body["requests"]) == 3
        # Ensure there are no nested bodies implying multiple API calls
        assert not any("body" in req for req in body["requests"])
    finally:
        if original is None:
            os.environ.pop("KYLO_SHEETS_DRY_RUN", None)
        else:
            os.environ["KYLO_SHEETS_DRY_RUN"] = original


