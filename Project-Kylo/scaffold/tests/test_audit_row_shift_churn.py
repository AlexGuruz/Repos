from __future__ import annotations

from services.audit.row_model import RowRecord, make_business_line_uid, make_row_key
from services.audit.sheet_diff import diff_registries
from services.audit.tick import _sheet_side_effect_events, _suppress_stable_shift_churn
from services.audit.txn_diff import build_business_line_registry, diff_business_line_registries


def _row(row_index: int, description: str, amount_cents: int = 1000) -> RowRecord:
    sid = "spreadsheet-1"
    tab = "TRANSACTIONS"
    company = "NUGZ"
    posted_date = "2026-08-15"
    return RowRecord(
        row_key=make_row_key(sid, tab, row_index),
        source_spreadsheet_id=sid,
        source_tab=tab,
        row_index_0based=row_index,
        company_id=company,
        posted_date=posted_date,
        description=description,
        amount_cents=amount_cents,
        first_seen_at="2026-08-15T00:00:00Z",
        content_fp=f"{posted_date}|{company}|{amount_cents}|{description}",
        business_line_uid=make_business_line_uid(sid, tab, company, posted_date, description),
    )


def test_stable_business_lines_suppress_row_index_insert_churn():
    previous_rows = [_row(1, "rent"), _row(2, "payroll")]
    current_rows = [_row(2, "rent"), _row(3, "payroll")]
    previous = {r.row_key: r for r in previous_rows}
    current = {r.row_key: r for r in current_rows}
    previous_bl = build_business_line_registry(previous_rows)
    current_bl = build_business_line_registry(current_rows)

    row_events = diff_registries(previous, current, ts="2026-08-15T01:00:00Z")
    stable_events = diff_business_line_registries(previous_bl, current_bl, ts="2026-08-15T01:00:00Z")
    filtered = _suppress_stable_shift_churn(row_events + stable_events, previous, current, previous_bl, current_bl)

    assert {ev.event for ev in filtered} == {"ROW_SHIFTED"}
    assert _sheet_side_effect_events(filtered) == []


def test_stable_business_line_amount_change_survives_shift_filter():
    previous_rows = [_row(1, "rent"), _row(2, "payroll", 1000)]
    current_rows = [_row(2, "rent"), _row(3, "payroll", 2500)]
    previous = {r.row_key: r for r in previous_rows}
    current = {r.row_key: r for r in current_rows}
    previous_bl = build_business_line_registry(previous_rows)
    current_bl = build_business_line_registry(current_rows)

    row_events = diff_registries(previous, current, ts="2026-08-15T01:00:00Z")
    stable_events = diff_business_line_registries(previous_bl, current_bl, ts="2026-08-15T01:00:00Z")
    filtered = _suppress_stable_shift_churn(row_events + stable_events, previous, current, previous_bl, current_bl)

    assert any(ev.event == "ROW_CHANGED" and ev.changed_field == "amount" for ev in filtered)
    assert any(ev.event == "ROW_CHANGED" and ev.changed_field == "amount" for ev in _sheet_side_effect_events(filtered))
