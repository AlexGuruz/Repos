from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from scripts.build_projection_by_category_brand import iter_unique_order_items_in_window


def test_unique_order_items_skip_duplicate_object_ids() -> None:
    tz = ZoneInfo("America/Chicago")
    raw = [
        {"objectId": "oi-1", "SoldAt": "2026-04-01T15:00:00.000Z", "GrossPrice": 1000},
        {"objectId": "oi-1", "SoldAt": "2026-04-01T15:00:00.000Z", "GrossPrice": 1000},
        {"objectId": "oi-2", "SoldAt": "2026-04-02T15:00:00.000Z", "GrossPrice": 1500},
    ]

    rows = iter_unique_order_items_in_window(raw, set(), tz, date(2026, 4, 1), date(2026, 4, 2))

    assert [row["objectId"] for row, _ in rows] == ["oi-1", "oi-2"]
