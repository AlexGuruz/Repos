from __future__ import annotations

import re
import hashlib
import json
from typing import Dict, List, Set, Tuple

from services.audit.row_model import ChangeEvent
from services.common.retry import google_api_execute


def _finding_label(event: ChangeEvent) -> str:
    if "FALSE_PAYROLL" in event.anomalies or "INFLATED_PAYROLL_APPEARANCE" in event.anomalies:
        return "FALSE TRANSACTION"
    if event.event == "ROW_INSERTED" or "ROW_INSERTED" in event.anomalies:
        return "INSERTED ROW"
    if event.changed_field == "amount" or "AMOUNT_REVISION" in event.anomalies:
        return "CHANGED AMOUNT"
    if event.event == "ANOMALY":
        return "ANOMALY"
    return event.event.replace("_", " ")


def _tab_quote(tab: str) -> str:
    return "'" + tab.replace("'", "''") + "'" if re.search(r"[^A-Za-z0-9_]", tab) else tab


def _event_note_id(event: ChangeEvent) -> str:
    material = (
        event.source_spreadsheet_id,
        event.source_tab,
        int(event.sheet_row or 0),
        event.row_key,
        event.event,
        event.changed_field,
        event.before,
        event.after,
        tuple(event.anomalies or []),
        event.posted_date,
        event.description,
        int(event.amount_cents or 0),
        event.txn_uid,
        event.business_line_uid,
    )
    payload = json.dumps(material, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def write_audit_notes(
    service,
    events: List[ChangeEvent],
    *,
    note_column: str = "G",
    case_id: str = "LIVE-AUDIT",
) -> int:
    """Write KYLO-AUDIT-SYSTEM notes to intake Column G; preserve prior Kylo posting note when present."""
    if not events:
        return 0

    by_sid: Dict[str, List[Tuple[str, ChangeEvent]]] = {}
    seen: Set[str] = set()
    for ev in events:
        if ev.event == "ROW_REMOVED":
            continue
        sig = f"{ev.source_spreadsheet_id}|{ev.sheet_row}|{ev.event}|{ev.changed_field}"
        if sig in seen:
            continue
        seen.add(sig)
        cell = f"{_tab_quote(ev.source_tab)}!{note_column}{ev.sheet_row}"
        by_sid.setdefault(ev.source_spreadsheet_id, []).append((cell, ev))

    written = 0
    for sid, items in by_sid.items():
        ranges = [c for c, _ in items]
        existing: Dict[str, str] = {}
        try:
            resp = google_api_execute(
                service.spreadsheets().values().batchGet(spreadsheetId=sid, ranges=ranges),
                label="audit:notes_read_existing",
            )
            for vr in resp.get("valueRanges") or []:
                rng = str(vr.get("range") or "")
                key = rng.split("!")[-1] if "!" in rng else rng
                vals = vr.get("values") or []
                existing[key] = str(vals[0][0]) if vals and vals[0] else ""
        except Exception:
            pass

        batch: List[dict] = []
        for cell_range, ev in items:
            cell_key = cell_range.split("!")[-1]
            prior = existing.get(cell_key, "")
            label = _finding_label(ev)
            note_id = _event_note_id(ev)
            if note_id and note_id in prior:
                continue
            amt = ev.amount_cents / 100.0
            amt_str = f"(${abs(amt):,.2f})" if amt < 0 else f"${amt:,.2f}"
            parts = [
                "KYLO-AUDIT-SYSTEM",
                case_id,
                f"id={note_id}",
                label,
                f"{ev.posted_date} {ev.company_id} {ev.description} {amt_str}",
            ]
            if ev.before and ev.after and ev.changed_field:
                parts.append(f"{ev.changed_field}: {ev.before} -> {ev.after}")
            parts.extend([f"detected {ev.ts[:19]}", "automated forensic audit", "NOT manual user entry"])
            audit_line = " | ".join(parts)[:450]
            if prior and prior.strip() and not prior.startswith("KYLO-AUDIT-SYSTEM"):
                combined = f"{prior} || {audit_line}"[:500]
            else:
                combined = audit_line[:500]
            if combined == prior:
                continue
            batch.append({"range": cell_range, "values": [[combined]]})

        if not batch:
            continue
        try:
            google_api_execute(
                service.spreadsheets().values().batchUpdate(
                    spreadsheetId=sid,
                    body={"valueInputOption": "USER_ENTERED", "data": batch},
                ),
                label="audit:notes_batch",
            )
            written += len(batch)
        except Exception as e:
            print(f"[AUDIT] WARN: could not write audit notes: {e}")

    if written:
        print(f"[AUDIT] Wrote {written} Kylo system audit note(s) to intake Column {note_column}")
    return written


__all__ = ["write_audit_notes"]
