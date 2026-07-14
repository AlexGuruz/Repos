from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from scripts.build_projection_by_category_brand import _iter_unique_projection_rows


def test_projection_rows_dedupe_duplicate_order_items_after_date_filter() -> None:
    seen: set[str] = set()
    tz = ZoneInfo("America/Chicago")
    rows = [
        {
            "objectId": "line-1",
            "SoldAt": "2026-07-13T12:00:00Z",
            "GrossPrice": 1000,
        },
        {
            "objectId": "line-1",
            "SoldAt": "2026-07-13T12:00:00Z",
            "GrossPrice": 1000,
        },
    ]

    accepted = list(
        _iter_unique_projection_rows(
            rows,
            seen,
            tz,
            report_start_local=date(2026, 7, 13),
            report_end_local=date(2026, 7, 13),
        )
    )

    assert [row["objectId"] for row, _local_day in accepted] == ["line-1"]
    assert seen == {"objectId:line-1"}
