from __future__ import annotations

from typing import Dict, List, Optional

from services.audit.row_model import ChangeEvent, RowRecord, sheet_row_1based


def diff_business_line_registries(
    before: Dict[str, RowRecord],
    after: Dict[str, RowRecord],
    *,
    ts: str,
) -> List[ChangeEvent]:
    """Diff by stable business_line_uid — catches amount edits even when row index shifts."""
    events: List[ChangeEvent] = []
    before_keys = set(before.keys())
    after_keys = set(after.keys())

    for bl in sorted(after_keys - before_keys):
        r = after[bl]
        events.append(
            ChangeEvent(
                ts=ts,
                event="ROW_INSERTED",
                row_key=r.row_key,
                source_spreadsheet_id=r.source_spreadsheet_id,
                source_tab=r.source_tab,
                sheet_row=sheet_row_1based(r.row_index_0based),
                company_id=r.company_id,
                changed_field="business_line",
                before="",
                after=f"date={r.posted_date} amount={r.amount_cents/100:.2f}",
                anomalies=["ROW_INSERTED", "STABLE_UID_NEW"],
                posted_date=r.posted_date,
                description=r.description,
                amount_cents=r.amount_cents,
                txn_uid=r.txn_uid,
                business_line_uid=bl,
            )
        )

    for bl in sorted(before_keys & after_keys):
        b = before[bl]
        a = after[bl]
        base = dict(
            row_key=a.row_key,
            source_spreadsheet_id=a.source_spreadsheet_id,
            source_tab=a.source_tab,
            sheet_row=sheet_row_1based(a.row_index_0based),
            company_id=a.company_id,
            posted_date=a.posted_date,
            description=a.description,
            amount_cents=a.amount_cents,
            txn_uid=a.txn_uid,
            business_line_uid=bl,
        )
        if b.amount_cents != a.amount_cents:
            anom = ["AMOUNT_REVISION", "STABLE_UID_AMOUNT_CHANGE"]
            if b.posted_flag or b.kylo_posted_amount_cents is not None:
                anom.append("POSTED_AMOUNT_EDIT")
            events.append(
                ChangeEvent(
                    ts=ts,
                    event="ROW_CHANGED",
                    changed_field="amount",
                    before=f"{b.amount_cents/100:.2f}",
                    after=f"{a.amount_cents/100:.2f}",
                    anomalies=anom,
                    **base,
                )
            )
        if b.row_index_0based != a.row_index_0based:
            events.append(
                ChangeEvent(
                    ts=ts,
                    event="ROW_SHIFTED",
                    changed_field="position",
                    before=str(b.row_index_0based),
                    after=str(a.row_index_0based),
                    anomalies=["CONTENT_SHIFTED"],
                    **base,
                )
            )

    return events


def build_business_line_registry(rows: List[RowRecord]) -> Dict[str, RowRecord]:
    out: Dict[str, RowRecord] = {}
    for r in rows:
        bl = str(r.business_line_uid or "").strip()
        if bl:
            out[bl] = r
    return out


def merge_business_line_registry(
    previous: Dict[str, RowRecord],
    current: Dict[str, RowRecord],
    *,
    ts: str,
) -> Dict[str, RowRecord]:
    out: Dict[str, RowRecord] = {}
    for bl, r in current.items():
        prev = previous.get(bl)
        first_seen = (prev.first_seen_at if prev else "") or ts
        kylo_at = (prev.kylo_posted_at if prev else "") or r.kylo_posted_at
        kylo_amt = r.kylo_posted_amount_cents if r.kylo_posted_amount_cents is not None else (
            prev.kylo_posted_amount_cents if prev else None
        )
        changed_at = ts if prev and (
            prev.amount_cents != r.amount_cents or prev.row_index_0based != r.row_index_0based
        ) else (prev.last_changed_at if prev else "")
        out[bl] = RowRecord(
            row_key=r.row_key,
            source_spreadsheet_id=r.source_spreadsheet_id,
            source_tab=r.source_tab,
            row_index_0based=r.row_index_0based,
            company_id=r.company_id,
            posted_date=r.posted_date,
            description=r.description,
            amount_cents=r.amount_cents,
            posted_flag=r.posted_flag,
            first_seen_at=first_seen,
            content_fp=r.content_fp,
            txn_uid=r.txn_uid,
            business_line_uid=bl,
            kylo_posted_at=kylo_at,
            kylo_posted_amount_cents=kylo_amt,
            last_changed_at=changed_at,
        )
    return out


__all__ = [
    "build_business_line_registry",
    "diff_business_line_registries",
    "merge_business_line_registry",
]
