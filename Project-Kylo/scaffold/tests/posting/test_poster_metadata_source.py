from __future__ import annotations

from pathlib import Path


def test_poster_audit_metadata_uses_per_matched_write_fields() -> None:
    source = Path("services/posting/jgdtruth_poster.py").read_text(encoding="utf-8")

    assert "posted_date=posted_date" in source
    assert "description=description" in source
    assert '"posted_date": posted_date' in source
    assert '"description": description' in source

    stale_flagged_start = source.index("flagged = is_txn_flagged(")
    stale_flagged_end = source.index("amount_cents=amount_cents", stale_flagged_start)
    flagged_block = source[stale_flagged_start:stale_flagged_end]
    assert "str(dt or" not in flagged_block
    assert "str(src or" not in flagged_block
