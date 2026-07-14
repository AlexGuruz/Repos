from __future__ import annotations

import unittest
from datetime import date
from zoneinfo import ZoneInfo

from scripts.build_projection_by_category_brand import _accept_unique_order_item_in_window


class ProjectionOrderItemDedupeTests(unittest.TestCase):
    def test_accepts_order_item_only_once_inside_window(self) -> None:
        seen: set[str] = set()
        tz = ZoneInfo("America/Chicago")
        node = {"objectId": "order-line-1", "SoldAt": "2026-07-10T15:00:00.000Z"}

        self.assertTrue(
            _accept_unique_order_item_in_window(
                node,
                seen=seen,
                tz=tz,
                report_start_local=date(2026, 7, 1),
                report_end_local=date(2026, 7, 31),
            )
        )
        self.assertFalse(
            _accept_unique_order_item_in_window(
                dict(node),
                seen=seen,
                tz=tz,
                report_start_local=date(2026, 7, 1),
                report_end_local=date(2026, 7, 31),
            )
        )

    def test_invalid_or_out_of_window_rows_do_not_claim_key(self) -> None:
        seen: set[str] = set()
        tz = ZoneInfo("America/Chicago")
        invalid = {"objectId": "order-line-2", "SoldAt": "not-a-date"}
        valid = {"objectId": "order-line-2", "SoldAt": "2026-07-10T15:00:00.000Z"}
        out_of_window = {"objectId": "order-line-3", "SoldAt": "2026-08-10T15:00:00.000Z"}

        self.assertFalse(
            _accept_unique_order_item_in_window(
                invalid,
                seen=seen,
                tz=tz,
                report_start_local=date(2026, 7, 1),
                report_end_local=date(2026, 7, 31),
            )
        )
        self.assertTrue(
            _accept_unique_order_item_in_window(
                valid,
                seen=seen,
                tz=tz,
                report_start_local=date(2026, 7, 1),
                report_end_local=date(2026, 7, 31),
            )
        )
        self.assertFalse(
            _accept_unique_order_item_in_window(
                out_of_window,
                seen=seen,
                tz=tz,
                report_start_local=date(2026, 7, 1),
                report_end_local=date(2026, 7, 31),
            )
        )
        self.assertNotIn("objectId:order-line-3", seen)


if __name__ == "__main__":
    unittest.main()
