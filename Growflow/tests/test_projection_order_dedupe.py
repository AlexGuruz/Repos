from __future__ import annotations

import inspect

from scripts import build_projection_by_category_brand


def test_projection_marks_order_item_seen_before_aggregation() -> None:
    src = inspect.getsource(build_projection_by_category_brand.main)
    guard_idx = src.index("if k in seen:")
    seen_idx = src.index("seen.add(k)", guard_idx)
    append_idx = src.index("validation_rows.append(n)", guard_idx)
    aggregate_idx = src.index("pair_gross[key_bc] += gp", guard_idx)

    assert guard_idx < seen_idx < append_idx < aggregate_idx
