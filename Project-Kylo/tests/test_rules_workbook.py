from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from services.common.rules_workbook import (
    extract_spreadsheet_id,
    get_rules_management_spreadsheet_id,
)


class RulesWorkbookTests(unittest.TestCase):
    def test_extracts_spreadsheet_id_from_url(self) -> None:
        self.assertEqual(
            extract_spreadsheet_id("https://docs.google.com/spreadsheets/d/abc_DEF-123/edit#gid=0"),
            "abc_DEF-123",
        )

    def test_accepts_direct_spreadsheet_id(self) -> None:
        self.assertEqual(
            extract_spreadsheet_id("1MZqpmK6TO7Y9HkMSWPHTIwS3bIZ407sPxSy6R8bZUnE"),
            "1MZqpmK6TO7Y9HkMSWPHTIwS3bIZ407sPxSy6R8bZUnE",
        )

    def test_resolves_plain_nested_dict_config(self) -> None:
        cfg = {
            "rules": {
                "management_workbook_url": (
                    "https://docs.google.com/spreadsheets/d/"
                    "1oNVc-C03ePqLNE76sRUldzpLYsJWb2fo92rkM0_fqNE/edit"
                )
            }
        }
        with patch.dict(os.environ, {"KYLO_RULES_MANAGEMENT_SPREADSHEET_ID": ""}, clear=False):
            self.assertEqual(
                get_rules_management_spreadsheet_id(cfg),
                "1oNVc-C03ePqLNE76sRUldzpLYsJWb2fo92rkM0_fqNE",
            )

    def test_env_override_wins(self) -> None:
        cfg = {"rules": {"management_spreadsheet_id": "1oNVc-C03ePqLNE76sRUldzpLYsJWb2fo92rkM0_fqNE"}}
        with patch.dict(
            os.environ,
            {"KYLO_RULES_MANAGEMENT_SPREADSHEET_ID": "1MZqpmK6TO7Y9HkMSWPHTIwS3bIZ407sPxSy6R8bZUnE"},
            clear=False,
        ):
            self.assertEqual(
                get_rules_management_spreadsheet_id(cfg),
                "1MZqpmK6TO7Y9HkMSWPHTIwS3bIZ407sPxSy6R8bZUnE",
            )


if __name__ == "__main__":
    unittest.main()
