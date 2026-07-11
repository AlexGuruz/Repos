from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Set

from dataclasses import replace

from services.audit.highlights import apply_target_cell_highlights
from services.audit.logger import append_post_event
from services.audit.paths import audit_jsonl_path, business_line_registry_path
from services.audit.row_model import make_business_line_uid
from services.audit.snapshot import load_row_registry, save_row_registry


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def format_post_note(
    amount_cents: int,
    tab: str,
    header: str,
    date_key: str,
    *,
    posted_at: Optional[str] = None,
    flagged: bool = False,
) -> str:
    ts = posted_at or _utc_now_iso()
    ts_short = ts[:19].replace("T", " ")
    msg = f"Posted {amount_cents / 100.0:.2f} at {ts_short} -> {tab}/{header} {date_key}"
    if flagged:
        msg += " | KYLO-FLAGGED"
    return msg


def is_txn_flagged(
    *,
    source_sid: str,
    source_tab: str,
    company_id: str,
    posted_date: str,
    description: str,
    amount_cents: int,
    instance_id: str,
) -> bool:
    """Check business-line registry for open anomalies on this transaction line."""
    reg = load_row_registry(business_line_registry_path(instance_id))
    bl = make_business_line_uid(source_sid, source_tab, company_id, posted_date, description)
    rec = reg.get(bl)
    if not rec:
        return False
    if rec.kylo_posted_amount_cents is not None and rec.kylo_posted_amount_cents != amount_cents:
        return True
    if rec.last_changed_at and rec.kylo_posted_at and rec.last_changed_at > rec.kylo_posted_at:
        return True
    return False


def record_successful_post(
    *,
    instance_id: str,
    txn_uid: str,
    source_sid: str,
    source_tab: str,
    row0: int,
    company_id: str,
    posted_date: str,
    description: str,
    amount_cents: int,
    target_a1: str,
    note: str,
    flagged: bool = False,
) -> None:
    """Update registries and audit log after a successful post write."""
    ts = _utc_now_iso()
    bl = make_business_line_uid(source_sid, source_tab, company_id, posted_date, description)
    for path in (business_line_registry_path(instance_id),):
        reg = load_row_registry(path)
        if bl in reg:
            rec = reg[bl]
            reg[bl] = replace(
                rec,
                kylo_posted_at=ts,
                kylo_posted_amount_cents=amount_cents,
            )
            save_row_registry(path, reg)

    append_post_event(
        audit_jsonl_path(instance_id),
        instance_id=instance_id,
        txn_uid=txn_uid,
        business_line_uid=bl,
        source_sid=source_sid,
        source_tab=source_tab,
        sheet_row=row0 + 1,
        amount_cents=amount_cents,
        target_a1=target_a1,
        note=note,
        flagged=flagged,
    )


def apply_flagged_target_highlights(
    service,
    target_spreadsheet_id: str,
    flagged_ranges: Set[str],
    cfg: Any,
) -> int:
    if not flagged_ranges:
        return 0
    return apply_target_cell_highlights(service, target_spreadsheet_id, sorted(flagged_ranges), cfg)


__all__ = [
    "apply_flagged_target_highlights",
    "format_post_note",
    "is_txn_flagged",
    "record_successful_post",
]
