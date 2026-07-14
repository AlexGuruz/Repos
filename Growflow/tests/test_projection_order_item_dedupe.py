from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from lib.growflow_queries import ORDER_ITEMS_QUERY, ORDER_ITEMS_QUERY_NO_PACKAGE
from scripts import build_projection_by_category_brand as projection


def test_projection_window_filter_dedupes_seen_order_items() -> None:
    rows = [
        {"objectId": "oi-1", "SoldAt": "2026-07-01T12:00:00Z", "GrossPrice": 1000},
        {"objectId": "oi-1", "SoldAt": "2026-07-01T12:00:00Z", "GrossPrice": 1000},
        {"objectId": "oi-2", "SoldAt": "2026-07-02T12:00:00Z", "GrossPrice": 2000},
    ]
    seen: set[str] = set()

    filtered = projection.filter_unique_order_items_for_projection_window(
        rows,
        seen,
        report_start_local=date(2026, 7, 1),
        report_end_local=date(2026, 7, 31),
        tz=ZoneInfo("UTC"),
    )

    assert [row["objectId"] for row in filtered] == ["oi-1", "oi-2"]
    assert seen == {"objectId:oi-1", "objectId:oi-2"}


def test_fetch_chunk_falls_back_when_package_field_is_rejected(monkeypatch) -> None:
    calls: list[str] = []

    def fake_fetch_paginated(_field, query, _variables, *, credentials_path=None):
        calls.append(query)
        if query == ORDER_ITEMS_QUERY:
            raise RuntimeError('Cannot query field "Package" on type "OrderItems"')
        return [{"objectId": "oi-1", "SoldAt": "2026-07-01T12:00:00Z"}]

    monkeypatch.setattr(projection, "fetch_paginated", fake_fetch_paginated)

    rows, query_used = projection._fetch_chunk(
        oi_query=ORDER_ITEMS_QUERY,
        where={},
        creds=None,
        chunk_idx=1,
        retries=1,
    )

    assert rows == [{"objectId": "oi-1", "SoldAt": "2026-07-01T12:00:00Z"}]
    assert query_used == ORDER_ITEMS_QUERY_NO_PACKAGE
    assert calls == [ORDER_ITEMS_QUERY, ORDER_ITEMS_QUERY_NO_PACKAGE]
