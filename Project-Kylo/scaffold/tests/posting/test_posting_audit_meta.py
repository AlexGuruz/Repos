from __future__ import annotations

from services.posting.jgdtruth_poster import _post_meta_key


def test_post_meta_key_keeps_same_target_source_rows_distinct() -> None:
    target_a1 = "'NUGZ COG'!F12"

    first = _post_meta_key("source-sheet", "TRANSACTIONS", 10, target_a1)
    second = _post_meta_key("source-sheet", "TRANSACTIONS", 11, target_a1)

    assert first != second
    assert first[-1] == target_a1
    assert second[-1] == target_a1
