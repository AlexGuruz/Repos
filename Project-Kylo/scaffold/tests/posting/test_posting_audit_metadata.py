from __future__ import annotations

from services.posting.jgdtruth_poster import _build_post_audit_meta, _post_success_key


def test_post_success_key_distinguishes_rows_with_same_target_cell():
    first = _post_success_key("source-sheet", "TRANSACTIONS", 10, "'NUGZ EXPENSES'!B20")
    second = _post_success_key("source-sheet", "TRANSACTIONS", 11, "'NUGZ EXPENSES'!B20")

    assert first != second


def test_post_audit_meta_preserves_row_specific_date_and_description():
    meta = _build_post_audit_meta(
        txn_uid="txn-1",
        source_sid="source-sheet",
        src_tab="BANK",
        row0=10,
        company_id="NUGZ",
        posted_date="2026-04-03",
        description="first row",
        amount_cents=1234,
        flagged=True,
    )

    assert meta["posted_date"] == "2026-04-03"
    assert meta["description"] == "first row"
    assert meta["source_tab"] == "BANK"
    assert meta["flagged"] is True
