from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from services.audit.backlog import write_backlog_notes
from services.common.rules_workbook import extract_spreadsheet_id, get_rules_management_spreadsheet_id


class _Request:
    def __init__(self, response):
        self.response = response

    def execute(self):
        return self.response


class _Values:
    def __init__(self):
        self.batch_update_body = None

    def batchGet(self, **kwargs):
        return _Request({"valueRanges": [{"range": "TRANSACTIONS!G10", "values": [["manual CPA note"]]}]})

    def batchUpdate(self, **kwargs):
        self.batch_update_body = kwargs["body"]
        return _Request({})


class _Spreadsheets:
    def __init__(self):
        self.values_api = _Values()

    def values(self):
        return self.values_api


class _Service:
    def __init__(self):
        self.spreadsheets_api = _Spreadsheets()

    def spreadsheets(self):
        return self.spreadsheets_api


class RulesWorkbookTests(unittest.TestCase):
    def test_extract_spreadsheet_id_from_url(self) -> None:
        self.assertEqual(
            extract_spreadsheet_id("https://docs.google.com/spreadsheets/d/abc123/edit#gid=0"),
            "abc123",
        )

    def test_env_rules_management_id_wins(self) -> None:
        with patch.dict(os.environ, {"KYLO_RULES_MANAGEMENT_SPREADSHEET_ID": "env-id"}, clear=False):
            self.assertEqual(get_rules_management_spreadsheet_id({"rules": {"management_spreadsheet_id": "cfg-id"}}), "env-id")


class BacklogNotesTests(unittest.TestCase):
    def test_backlog_notes_preserve_manual_note(self) -> None:
        service = _Service()
        manifest = {
            "case_id": "CASE-1",
            "detected_at": "2026-07-13T20:00:00Z",
            "intake": {"spreadsheet_id": "sid", "tab": "TRANSACTIONS"},
            "entries": [
                {
                    "sheet_row": 10,
                    "company_id": "JGD",
                    "posted_date": "2026-01-01",
                    "description": "Payroll",
                    "amount_cents": -12345,
                    "anomalies": ["FALSE_PAYROLL"],
                }
            ],
        }

        written = write_backlog_notes(service, manifest)

        self.assertEqual(written, 1)
        body = service.spreadsheets_api.values_api.batch_update_body
        value = body["data"][0]["values"][0][0]
        self.assertIn("manual CPA note || KYLO-AUDIT-SYSTEM", value)


if __name__ == "__main__":
    unittest.main()
