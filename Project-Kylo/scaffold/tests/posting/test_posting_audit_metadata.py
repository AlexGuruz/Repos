from __future__ import annotations

from services.posting.jgdtruth_poster import MatchedWrite, _post_meta_from_write, _post_meta_key


def test_post_meta_is_keyed_by_source_row_not_target_cell():
    target_a1 = "'NUGZ COG'!B20"
    first = MatchedWrite(
        tab="NUGZ COG",
        header="COG",
        date_key="1/1/26",
        amount_cents=1000,
        source_tab="TRANSACTIONS",
        row0=2,
        txn_uid="txn-1",
        source_sid="source-sheet",
        for_marking=True,
        posted_date="2026-01-01",
        description="First txn",
    )
    second = MatchedWrite(
        tab="NUGZ COG",
        header="COG",
        date_key="1/1/26",
        amount_cents=2500,
        source_tab="BANK",
        row0=7,
        txn_uid="txn-2",
        source_sid="source-sheet",
        for_marking=True,
        posted_date="2026-01-02",
        description="Second txn",
    )

    meta_by_source = {}
    for write in (first, second):
        key, meta = _post_meta_from_write(write, target_a1, company_id="NUGZ", flagged=False)
        meta_by_source[key] = meta

    assert _post_meta_key("source-sheet", "TRANSACTIONS", 2, target_a1) in meta_by_source
    assert _post_meta_key("source-sheet", "BANK", 7, target_a1) in meta_by_source
    assert len(meta_by_source) == 2
    assert meta_by_source[_post_meta_key("source-sheet", "TRANSACTIONS", 2, target_a1)]["description"] == "First txn"
    assert meta_by_source[_post_meta_key("source-sheet", "BANK", 7, target_a1)]["posted_date"] == "2026-01-02"
