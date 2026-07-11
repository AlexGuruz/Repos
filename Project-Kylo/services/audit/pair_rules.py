from __future__ import annotations

import re
from typing import List, Optional, Tuple

from services.audit.row_model import ChangeEvent, RowRecord, sheet_row_1based


def _is_from_bank(desc: str) -> bool:
    return str(desc or "").strip().upper().startswith("FROM BANK")


def _is_payroll(desc: str) -> bool:
    return bool(re.match(r"^PAYROLL\s+\d+", str(desc or "").strip().upper()))


def detect_from_bank_payroll_pairs(
    rows: List[RowRecord],
    *,
    ts: str,
    max_pair_distance: int = 3,
) -> List[ChangeEvent]:
    """Detect zero-net FROM BANK + PAYROLL pairs (false payroll appearance)."""
    events: List[ChangeEvent] = []
    by_tab: dict[str, List[RowRecord]] = {}
    for r in rows:
        key = f"{r.source_spreadsheet_id}|{r.source_tab.upper()}"
        by_tab.setdefault(key, []).append(r)

    for tab_rows in by_tab.values():
        ordered = sorted(tab_rows, key=lambda x: x.row_index_0based)
        n = len(ordered)
        for i, a in enumerate(ordered):
            if not _is_from_bank(a.description):
                continue
            for j in range(i + 1, min(i + 1 + max_pair_distance, n)):
                b = ordered[j]
                if not _is_payroll(b.description):
                    continue
                if abs(a.amount_cents) != abs(b.amount_cents):
                    continue
                if a.amount_cents <= 0 or b.amount_cents >= 0:
                    continue
                anomalies = ["FROM_BANK_PAIR", "FALSE_PAYROLL", "INFLATED_PAYROLL_APPEARANCE"]
                for rec, role in ((a, "FROM_BANK"), (b, "PAYROLL")):
                    events.append(
                        ChangeEvent(
                            ts=ts,
                            event="ANOMALY",
                            row_key=rec.row_key,
                            source_spreadsheet_id=rec.source_spreadsheet_id,
                            source_tab=rec.source_tab,
                            sheet_row=sheet_row_1based(rec.row_index_0based),
                            company_id=rec.company_id,
                            changed_field="payroll_pair",
                            before=role,
                            after=f"paired_row={sheet_row_1based(ordered[j].row_index_0based if role == 'FROM_BANK' else ordered[i].row_index_0based)}",
                            anomalies=anomalies,
                            posted_date=rec.posted_date,
                            description=rec.description,
                            amount_cents=rec.amount_cents,
                            txn_uid=rec.txn_uid,
                            business_line_uid=rec.business_line_uid,
                        )
                    )
                break
    return events


def detect_kylo_posted_amount_variance(
    rows: List[RowRecord],
    *,
    ts: str,
) -> List[ChangeEvent]:
    """Flag rows where current amount != amount Kylo recorded at post time."""
    events: List[ChangeEvent] = []
    for r in rows:
        if r.kylo_posted_amount_cents is None:
            continue
        if r.amount_cents == r.kylo_posted_amount_cents:
            continue
        events.append(
            ChangeEvent(
                ts=ts,
                event="ROW_CHANGED",
                row_key=r.row_key,
                source_spreadsheet_id=r.source_spreadsheet_id,
                source_tab=r.source_tab,
                sheet_row=sheet_row_1based(r.row_index_0based),
                company_id=r.company_id,
                changed_field="amount",
                before=f"{r.kylo_posted_amount_cents / 100:.2f}",
                after=f"{r.amount_cents / 100:.2f}",
                anomalies=["AMOUNT_REVISION", "KYLO_POSTED_VARIANCE"],
                posted_date=r.posted_date,
                description=r.description,
                amount_cents=r.amount_cents,
                txn_uid=r.txn_uid,
                business_line_uid=r.business_line_uid,
            )
        )
    return events


__all__ = [
    "detect_from_bank_payroll_pairs",
    "detect_kylo_posted_amount_variance",
]
