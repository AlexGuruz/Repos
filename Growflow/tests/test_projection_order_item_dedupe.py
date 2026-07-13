from scripts.build_projection_by_category_brand import _is_duplicate_order_item


def test_order_item_seen_set_is_populated() -> None:
    seen: set[str] = set()
    node = {"objectId": "order-line-1"}

    assert _is_duplicate_order_item(seen, node) is False
    assert "order-line-1" in seen
    assert _is_duplicate_order_item(seen, node) is True
