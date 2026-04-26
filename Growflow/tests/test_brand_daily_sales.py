"""Tests for lib.brand_daily_sales."""
from __future__ import annotations

from datetime import date, datetime, timezone

from zoneinfo import ZoneInfo

from lib.brand_daily_sales import (
    local_dates_inclusive,
    merge_brand_daily_window,
    brands_to_track_daily,
)


def test_local_dates_inclusive():
    d = date(2026, 4, 3)
    xs = local_dates_inclusive(d, 3)
    assert xs == [date(2026, 4, 1), date(2026, 4, 2), date(2026, 4, 3)]


def test_merge_brand_daily_window():
    tz = ZoneInfo("America/Chicago")
    acc: dict = {}
    day0 = date(2026, 4, 1)
    day1 = date(2026, 4, 2)
    end = date(2026, 4, 3)
    t0 = datetime(2026, 4, 1, 12, 0, 0, tzinfo=tz).astimezone(timezone.utc)
    t1 = datetime(2026, 4, 2, 12, 0, 0, tzinfo=tz).astimezone(timezone.utc)
    lines = [
        {"SoldAt": t0.isoformat().replace("+00:00", "Z"), "GrossPrice": 1000, "Product": {"Brand": {"Name": "A"}}},
        {"SoldAt": t1.isoformat().replace("+00:00", "Z"), "GrossPrice": 2000, "Product": {"Brand": {"Name": "A"}}},
    ]
    merge_brand_daily_window(lines, acc, tz, day0, end)
    assert acc[("A", day0)][0] == 1000
    assert acc[("A", day1)][0] == 2000
    assert ("A", end) not in acc


def test_brands_to_track_daily():
    acc = {("X", date(2026, 1, 1)): [1, 1]}
    class R:
        def __init__(self, b, inv=0, g14=0):
            self.brand = b
            self.inventory_cost_cents = inv
            self.gross_14d_cents = g14

    rows = [R("Y", inv=100), R("Z", g14=50)]
    s = brands_to_track_daily(acc, merit_rows=rows)
    assert s == {"X", "Y", "Z"}
