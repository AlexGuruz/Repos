from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from services.audit.row_model import ChangeEvent, RowRecord, content_fingerprint, sheet_row_1based


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso_date(posted_date: str) -> Optional[datetime]:
    s = str(posted_date or "").strip()
    if not s:
        return None
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        try:
            y, m, d = s.split("-")
            return datetime(int(y), int(m), int(d))
        except Exception:
            return None
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", s)
    if m:
        mo, da, yr = m.groups()
        y = int(yr)
        if y < 100:
            y += 2000
        try:
            return datetime(y, int(mo), int(da))
        except Exception:
            return None
    return None


def detect_date_inversions(rows: List[RowRecord]) -> List[Tuple[str, int, str, str]]:
    """Return (row_key, sheet_row, prev_date, cur_date) for each inversion within a tab."""
    by_tab: Dict[str, List[RowRecord]] = {}
    for r in rows:
        k = f"{r.source_spreadsheet_id}|{r.source_tab.upper()}"
        by_tab.setdefault(k, []).append(r)
    out: List[Tuple[str, int, str, str]] = []
    for tab_rows in by_tab.values():
        ordered = sorted(tab_rows, key=lambda x: x.row_index_0based)
        prev_dt: Optional[datetime] = None
        prev_date_str = ""
        for r in ordered:
            cur_dt = _parse_iso_date(r.posted_date)
            if cur_dt is None:
                continue
            if prev_dt is not None and cur_dt < prev_dt:
                out.append((r.row_key, sheet_row_1based(r.row_index_0based), prev_date_str, r.posted_date))
            prev_dt = cur_dt
            prev_date_str = r.posted_date
    return out


def _days_between(old: str, new_first_seen: str) -> Optional[int]:
    d_old = _parse_iso_date(old)
    if d_old is None:
        return None
    try:
        fs = datetime.fromisoformat(new_first_seen.replace("Z", "+00:00"))
    except Exception:
        return None
    return (fs.date() - d_old.date()).days


def diff_registries(
    before: Dict[str, RowRecord],
    after: Dict[str, RowRecord],
    *,
    ts: Optional[str] = None,
    late_arrival_min_posted_days: int = 14,
) -> List[ChangeEvent]:
    """Compare row registries and emit change events."""
    ts = ts or _utc_now_iso()
    events: List[ChangeEvent] = []

    before_keys = set(before.keys())
    after_keys = set(after.keys())

    def _stable_identity(record: RowRecord) -> str:
        if record.business_line_uid:
            return f"bl:{record.business_line_uid}"
        if record.content_fp:
            return f"fp:{record.content_fp}"
        return ""

    def _unique_identity_map(registry: Dict[str, RowRecord]) -> Dict[str, Tuple[str, RowRecord]]:
        grouped: Dict[str, List[Tuple[str, RowRecord]]] = {}
        for key, record in registry.items():
            ident = _stable_identity(record)
            if ident:
                grouped.setdefault(ident, []).append((key, record))
        return {ident: rows[0] for ident, rows in grouped.items() if len(rows) == 1}

    before_identity = _unique_identity_map(before)
    after_identity = _unique_identity_map(after)
    shifted_pairs: List[Tuple[str, str, RowRecord]] = []
    for ident, (old_key, _old_record) in before_identity.items():
        new = after_identity.get(ident)
        if not new:
            continue
        new_key, new_record = new
        if old_key != new_key:
            shifted_pairs.append((old_key, new_key, new_record))
    shifted_before_keys = {old_key for old_key, _new_key, _record in shifted_pairs}
    shifted_after_keys = {new_key for _old_key, new_key, _record in shifted_pairs}

    for rk in sorted(after_keys - before_keys):
        if rk in shifted_after_keys:
            continue
        r = after[rk]
        anomalies: List[str] = ["ROW_INSERTED"]
        if r.posted_flag:
            anomalies.append("NEW_ALREADY_POSTED")
        gap = _days_between(r.posted_date, r.first_seen_at or ts)
        if gap is not None and gap >= late_arrival_min_posted_days:
            anomalies.append("LATE_ARRIVAL")
        events.append(
            ChangeEvent(
                ts=ts,
                event="ROW_INSERTED",
                row_key=rk,
                source_spreadsheet_id=r.source_spreadsheet_id,
                source_tab=r.source_tab,
                sheet_row=sheet_row_1based(r.row_index_0based),
                company_id=r.company_id,
                changed_field="row",
                before="",
                after=f"date={r.posted_date} amount={r.amount_cents/100:.2f} source={r.description}",
                anomalies=anomalies,
                posted_date=r.posted_date,
                description=r.description,
                amount_cents=r.amount_cents,
                txn_uid=r.txn_uid,
                business_line_uid=r.business_line_uid,
            )
        )

    for rk in sorted(before_keys - after_keys):
        if rk in shifted_before_keys:
            continue
        r = before[rk]
        events.append(
            ChangeEvent(
                ts=ts,
                event="ROW_REMOVED",
                row_key=rk,
                source_spreadsheet_id=r.source_spreadsheet_id,
                source_tab=r.source_tab,
                sheet_row=sheet_row_1based(r.row_index_0based),
                company_id=r.company_id,
                changed_field="row",
                before=f"date={r.posted_date} amount={r.amount_cents/100:.2f}",
                after="",
                posted_date=r.posted_date,
                description=r.description,
                amount_cents=r.amount_cents,
            )
        )

    for rk in sorted(before_keys & after_keys):
        b = before[rk]
        a = after[rk]
        before_ident = _stable_identity(b)
        after_ident = _stable_identity(a)
        if (
            before_ident
            and after_ident
            and before_ident != after_ident
            and (before_ident in after_identity or after_ident in before_identity)
        ):
            continue
        base = dict(
            row_key=rk,
            source_spreadsheet_id=a.source_spreadsheet_id,
            source_tab=a.source_tab,
            sheet_row=sheet_row_1based(a.row_index_0based),
            company_id=a.company_id,
            posted_date=a.posted_date,
            description=a.description,
            amount_cents=a.amount_cents,
            txn_uid=a.txn_uid,
            business_line_uid=a.business_line_uid,
        )
        if b.amount_cents != a.amount_cents:
            events.append(
                ChangeEvent(
                    ts=ts,
                    event="ROW_CHANGED",
                    changed_field="amount",
                    before=f"{b.amount_cents/100:.2f}",
                    after=f"{a.amount_cents/100:.2f}",
                    anomalies=["AMOUNT_REVISION"] if b.posted_flag else [],
                    **base,
                )
            )
        if b.description != a.description:
            events.append(
                ChangeEvent(
                    ts=ts,
                    event="ROW_CHANGED",
                    changed_field="source",
                    before=b.description[:200],
                    after=a.description[:200],
                    **base,
                )
            )
        if b.posted_date != a.posted_date:
            anom = ["DATE_CHANGED"]
            if b.posted_flag:
                anom.append("BACKDATE_ON_POSTED")
            events.append(
                ChangeEvent(
                    ts=ts,
                    event="ROW_CHANGED",
                    changed_field="date",
                    before=b.posted_date,
                    after=a.posted_date,
                    anomalies=anom,
                    **base,
                )
            )
        if b.posted_flag != a.posted_flag:
            events.append(
                ChangeEvent(
                    ts=ts,
                    event="ROW_CHANGED",
                    changed_field="posted_flag",
                    before=str(b.posted_flag),
                    after=str(a.posted_flag),
                    anomalies=["POSTED_FLAG_TOGGLED"],
                    **base,
                )
            )
        if b.company_id != a.company_id:
            events.append(
                ChangeEvent(
                    ts=ts,
                    event="ROW_CHANGED",
                    changed_field="company_id",
                    before=b.company_id,
                    after=a.company_id,
                    **base,
                )
            )

    for old_key, new_key, r in shifted_pairs:
        events.append(
            ChangeEvent(
                ts=ts,
                event="ROW_SHIFTED",
                row_key=new_key,
                source_spreadsheet_id=r.source_spreadsheet_id,
                source_tab=r.source_tab,
                sheet_row=sheet_row_1based(r.row_index_0based),
                company_id=r.company_id,
                changed_field="position",
                before=old_key.split("|")[-1],
                after=str(r.row_index_0based),
                anomalies=["CONTENT_SHIFTED"],
                posted_date=r.posted_date,
                description=r.description,
                amount_cents=r.amount_cents,
                txn_uid=r.txn_uid,
                business_line_uid=r.business_line_uid,
            )
        )

    inversions = detect_date_inversions(list(after.values()))
    for row_key, sheet_row, prev_d, cur_d in inversions:
        r = after.get(row_key)
        if not r:
            continue
        events.append(
            ChangeEvent(
                ts=ts,
                event="ANOMALY",
                row_key=row_key,
                source_spreadsheet_id=r.source_spreadsheet_id,
                source_tab=r.source_tab,
                sheet_row=sheet_row,
                company_id=r.company_id,
                changed_field="date_order",
                before=prev_d,
                after=cur_d,
                anomalies=["DATE_INVERSION"],
                posted_date=r.posted_date,
                description=r.description,
                amount_cents=r.amount_cents,
            )
        )

    seen: set = set()
    deduped: List[ChangeEvent] = []
    for ev in events:
        sig = (ev.row_key, ev.event, ev.changed_field, ev.before, ev.after)
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(ev)
    return deduped


def merge_registry(
    previous: Dict[str, RowRecord],
    current: Dict[str, RowRecord],
    *,
    ts: str,
) -> Dict[str, RowRecord]:
    """Build new registry preserving first_seen_at."""
    out: Dict[str, RowRecord] = {}
    for rk, r in current.items():
        prev = previous.get(rk)
        first_seen = (prev.first_seen_at if prev else "") or ts
        out[rk] = RowRecord(
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
            content_fp=content_fingerprint(r.posted_date, r.company_id, r.description, r.amount_cents),
            txn_uid=r.txn_uid,
            business_line_uid=r.business_line_uid,
            kylo_posted_at=(prev.kylo_posted_at if prev else "") or r.kylo_posted_at,
            kylo_posted_amount_cents=(
                r.kylo_posted_amount_cents
                if r.kylo_posted_amount_cents is not None
                else (prev.kylo_posted_amount_cents if prev else None)
            ),
            last_changed_at=ts if prev and prev.amount_cents != r.amount_cents else (prev.last_changed_at if prev else ""),
        )
    return out


__all__ = ["detect_date_inversions", "diff_registries", "merge_registry"]
