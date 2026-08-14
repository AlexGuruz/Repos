"""Regression tests for projection order-item de-duplication."""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

_spec = importlib.util.spec_from_file_location(
    "build_projection",
    REPO / "scripts" / "build_projection_by_category_brand.py",
)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)


def _line(object_id: str, sold_at: str) -> dict:
    return {
        "objectId": object_id,
        "SoldAt": sold_at,
        "GrossPrice": 1000,
        "COG": 400,
        "Product": {
            "objectId": "prod-1",
            "Name": "Cartel 7pk Pre-Roll",
            "Brand": {"Name": "Cartel"},
            "Category": {"Name": "Pre-Rolls"},
        },
    }


def test_unique_order_item_local_date_skips_duplicate_order_lines() -> None:
    seen: set[str] = set()
    tz = ZoneInfo("America/Chicago")
    start = date(2026, 4, 1)
    end = date(2026, 4, 30)
    rows = [
        _line("order-line-1", "2026-04-10T15:00:00.000Z"),
        _line("order-line-1", "2026-04-10T15:00:00.000Z"),
        _line("order-line-2", "2026-04-11T15:00:00.000Z"),
    ]

    kept_dates = [
        _mod._unique_order_item_local_date(
            row,
            seen=seen,
            store_tz=tz,
            report_start_local=start,
            report_end_local=end,
        )
        for row in rows
    ]

    assert kept_dates == [date(2026, 4, 10), None, date(2026, 4, 11)]
    assert seen == {"objectId:order-line-1", "objectId:order-line-2"}


def test_unique_order_item_local_date_does_not_mark_out_of_window_rows_seen() -> None:
    seen: set[str] = set()
    tz = ZoneInfo("America/Chicago")
    start = date(2026, 4, 1)
    end = date(2026, 4, 30)

    outside = _mod._unique_order_item_local_date(
        _line("order-line-1", "2026-03-31T04:59:59.000Z"),
        seen=seen,
        store_tz=tz,
        report_start_local=start,
        report_end_local=end,
    )
    inside = _mod._unique_order_item_local_date(
        _line("order-line-1", "2026-04-01T05:00:00.000Z"),
        seen=seen,
        store_tz=tz,
        report_start_local=start,
        report_end_local=end,
    )

    assert outside is None
    assert inside == date(2026, 4, 1)
    assert seen == {"objectId:order-line-1"}
