from __future__ import annotations

from scripts.build_projection_by_category_brand import _mark_order_item_seen


def test_mark_order_item_seen_rejects_duplicate_keys() -> None:
    seen: set[str] = set()
    first = {"objectId": "order-line-1"}
    duplicate = {"objectId": "order-line-1"}
    second = {"objectId": "order-line-2"}

    assert _mark_order_item_seen(first, seen) is True
    assert _mark_order_item_seen(duplicate, seen) is False
    assert _mark_order_item_seen(second, seen) is True
    assert seen == {"objectId:order-line-1", "objectId:order-line-2"}
