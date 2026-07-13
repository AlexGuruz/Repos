from __future__ import annotations

from scripts import build_projection_by_category_brand as projection


def test_fetch_chunk_falls_back_when_package_field_is_missing(monkeypatch):
    calls = []

    def fake_fetch_paginated(connection_field, query, variables, *, credentials_path=None):
        calls.append(query)
        if query is projection.ORDER_ITEMS_QUERY:
            raise RuntimeError("Cannot query field 'Package' on type 'OrderItems'")
        if query is projection.ORDER_ITEMS_QUERY_NO_PACKAGE:
            return [{"objectId": "line-1", "SoldAt": "2026-07-01T00:00:00Z"}]
        raise AssertionError("unexpected query fallback")

    monkeypatch.setattr(projection, "fetch_paginated", fake_fetch_paginated)

    raw, used = projection._fetch_chunk(
        oi_query=projection.ORDER_ITEMS_QUERY,
        where={"SoldAt": {"greaterThanOrEqualTo": "2026-07-01T00:00:00Z"}},
        creds=None,
        chunk_idx=1,
        retries=1,
    )

    assert raw == [{"objectId": "line-1", "SoldAt": "2026-07-01T00:00:00Z"}]
    assert used is projection.ORDER_ITEMS_QUERY_NO_PACKAGE
    assert calls == [projection.ORDER_ITEMS_QUERY, projection.ORDER_ITEMS_QUERY_NO_PACKAGE]


def test_fetch_chunk_falls_back_when_brand_then_package_are_missing(monkeypatch):
    calls = []

    def fake_fetch_paginated(connection_field, query, variables, *, credentials_path=None):
        calls.append(query)
        if query is projection.ORDER_ITEMS_QUERY:
            raise RuntimeError("Cannot query field 'Brand' on type 'Products'")
        if query is projection.ORDER_ITEMS_QUERY_NO_BRAND:
            raise RuntimeError("Cannot query field 'Package' on type 'OrderItems'")
        if query is projection.ORDER_ITEMS_QUERY_NO_PACKAGE:
            raise RuntimeError("Cannot query field 'Brand' on type 'Products'")
        if query is projection.ORDER_ITEMS_QUERY_NO_BRAND_NO_PACKAGE:
            return [{"objectId": "line-1", "SoldAt": "2026-07-01T00:00:00Z"}]
        raise AssertionError("unexpected query fallback")

    monkeypatch.setattr(projection, "fetch_paginated", fake_fetch_paginated)

    raw, used = projection._fetch_chunk(
        oi_query=projection.ORDER_ITEMS_QUERY,
        where={"SoldAt": {"greaterThanOrEqualTo": "2026-07-01T00:00:00Z"}},
        creds=None,
        chunk_idx=1,
        retries=1,
    )

    assert raw == [{"objectId": "line-1", "SoldAt": "2026-07-01T00:00:00Z"}]
    assert used is projection.ORDER_ITEMS_QUERY_NO_BRAND_NO_PACKAGE
    assert calls == [
        projection.ORDER_ITEMS_QUERY,
        projection.ORDER_ITEMS_QUERY_NO_BRAND,
        projection.ORDER_ITEMS_QUERY_NO_PACKAGE,
        projection.ORDER_ITEMS_QUERY_NO_BRAND_NO_PACKAGE,
    ]
