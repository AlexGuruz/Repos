from __future__ import annotations

from pathlib import Path


def test_projection_order_item_loop_records_seen_keys():
    src = (Path(__file__).resolve().parents[1] / "scripts" / "build_projection_by_category_brand.py").read_text(
        encoding="utf-8"
    )
    guard = "if k in seen:\n                continue"
    add = "seen.add(k)"
    assert guard in src
    assert add in src[src.index(guard) :]
