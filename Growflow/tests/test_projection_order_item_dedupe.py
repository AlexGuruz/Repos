from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from scripts.build_projection_by_category_brand import _unique_order_items_in_local_window


def test_unique_order_items_dedupes_in_window_rows_across_chunks():
    tz = ZoneInfo("America/Chicago")
    seen: set[str] = set()
    first_chunk = [
        {"objectId": "outside", "SoldAt": "2026-05-31T23:00:00Z", "GrossPrice": 100},
        {"objectId": "dup", "SoldAt": "2026-06-01T15:00:00Z", "GrossPrice": 100},
    ]
    second_chunk = [
        {"objectId": "dup", "SoldAt": "2026-06-01T15:01:00Z", "GrossPrice": 100},
        {"objectId": "outside", "SoldAt": "2026-06-02T15:00:00Z", "GrossPrice": 100},
    ]

    kwargs = {
        "tz": tz,
        "report_start_local": date(2026, 6, 1),
        "report_end_local": date(2026, 6, 2),
        "seen": seen,
    }
    out = _unique_order_items_in_local_window(first_chunk, **kwargs)
    out.extend(_unique_order_items_in_local_window(second_chunk, **kwargs))

    assert [row["objectId"] for row in out] == ["dup", "outside"]
