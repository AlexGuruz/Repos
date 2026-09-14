from __future__ import annotations

from scripts import build_projection_by_category_brand as projection


def test_fetch_chunk_falls_back_when_package_field_is_rejected(monkeypatch):
    calls = []

    def fake_fetch_paginated(connection_field, query, variables, *, credentials_path=None):
        calls.append(query)
        if len(calls) == 1:
            raise RuntimeError('Cannot query field "Package" on type "OrderItems"')
        return [{"id": "order-item-1"}]

    monkeypatch.setattr(projection, "fetch_paginated", fake_fetch_paginated)

    rows, query_used = projection._fetch_chunk(
        oi_query=projection.ORDER_ITEMS_QUERY,
        where={"SoldAt": {"greaterThanOrEqualTo": "2026-01-01T00:00:00.000Z"}},
        creds=None,
        chunk_idx=1,
        retries=1,
    )

    assert rows == [{"id": "order-item-1"}]
    assert calls == [projection.ORDER_ITEMS_QUERY, projection.ORDER_ITEMS_QUERY_NO_PACKAGE]
    assert query_used == projection.ORDER_ITEMS_QUERY_NO_PACKAGE
