from __future__ import annotations

from services.audit.highlights import apply_audit_highlights
from services.audit.notes import write_audit_notes
from services.audit.row_model import ChangeEvent, RowRecord, make_row_key
from services.audit.sheet_diff import diff_registries


def _row(row0: int, description: str, amount_cents: int) -> RowRecord:
    return RowRecord.from_txn(
        {
            "source_spreadsheet_id": "sheet123",
            "source_tab": "TRANSACTIONS",
            "row_index_0based": row0,
            "company_id": "JGD",
            "posted_date": "2026-08-01",
            "description": description,
            "amount_cents": amount_cents,
        },
        first_seen_at="2026-08-14T03:00:00Z",
    )


def _registry(*records: RowRecord) -> dict[str, RowRecord]:
    return {r.row_key: r for r in records}


def test_diff_registries_treats_row_shift_as_shift_not_insert_delete():
    before = _registry(
        _row(10, "Alpha", 1000),
        _row(11, "Bravo", 2000),
    )
    after = _registry(
        _row(11, "Alpha", 1000),
        _row(12, "Bravo", 2000),
    )

    events = diff_registries(before, after, ts="2026-08-14T03:01:00Z")

    assert [ev.event for ev in events] == ["ROW_SHIFTED", "ROW_SHIFTED"]
    assert {ev.before for ev in events} == {"10", "11"}
    assert {ev.after for ev in events} == {"11", "12"}


def test_row_shift_events_do_not_write_notes_or_highlights():
    event = ChangeEvent(
        ts="2026-08-14T03:01:00Z",
        event="ROW_SHIFTED",
        row_key=make_row_key("sheet123", "TRANSACTIONS", 11),
        source_spreadsheet_id="sheet123",
        source_tab="TRANSACTIONS",
        sheet_row=12,
        company_id="JGD",
        changed_field="position",
        before="10",
        after="11",
    )

    assert write_audit_notes(object(), [event]) == 0
    assert apply_audit_highlights(object(), [event], {"audit": {"highlights": {"enabled": True}}}) == 0
