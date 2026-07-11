from __future__ import annotations

import csv
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from services.audit.highlights import apply_audit_highlights, clear_row_highlights
from services.audit.logger import append_audit_jsonl, append_audit_log
from services.audit.paths import audit_jsonl_path, audit_log_path, row_registry_path, snapshots_root
from services.audit.row_model import ChangeEvent, RowRecord, make_row_key
from services.audit.snapshot import load_row_registry, save_row_registry, save_tick_snapshot
from services.common.retry import google_api_execute


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_yaml(path: Path) -> Dict[str, Any]:
    try:
        import yaml
    except ImportError as e:
        raise RuntimeError("PyYAML required for backlog manifest") from e
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Invalid manifest: {path}")
    return data


def _fmt_amount(amount_cents: int) -> str:
    dollars = amount_cents / 100.0
    if dollars < 0:
        return f"(${abs(dollars):,.2f})"
    return f"${dollars:,.2f}"


def _finding_label(finding: str) -> str:
    labels = {
        "row_insertion": "INSERTED ROW",
        "amount_changed": "CHANGED AMOUNT",
        "false_payroll_transaction": "FALSE TRANSACTION — INSERTED ROW + EDITED AMOUNT",
    }
    return labels.get(finding, finding.replace("_", " ").upper())


def _resolve_estimated_edit(entry: Dict[str, Any], manifest: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    own = entry.get("estimated_edit")
    if isinstance(own, dict) and own:
        return own
    pair_group = str(entry.get("pair_group") or "").strip()
    if not pair_group:
        return None
    for group in manifest.get("row_groups") or []:
        if not isinstance(group, dict):
            continue
        if str(group.get("id") or "").strip() == pair_group:
            group_edit = group.get("estimated_edit")
            if isinstance(group_edit, dict) and group_edit:
                return group_edit
    return None


def _fmt_estimated_edit(estimated: Optional[Dict[str, Any]]) -> str:
    if not estimated or not isinstance(estimated, dict):
        return ""
    actor = str(estimated.get("suspected_actor") or "").strip()
    window = estimated.get("estimated_edit_window") or {}
    start = str(window.get("start") or estimated.get("window_start") or "").strip()
    end = str(window.get("end") or estimated.get("window_end") or "").strip()
    confidence = str(estimated.get("confidence") or "").strip().lower()
    parts: List[str] = []
    if start and end:
        parts.append(f"est. edit window: {start} to {end}")
    elif start:
        parts.append(f"est. edit window: after {start}")
    if actor:
        actor_note = f"actor: {actor}"
        evidence = estimated.get("evidence") or []
        if any(
            isinstance(ev, str) and "petty cash" in ev.lower() and "jjn" in ev.lower()
            for ev in evidence
        ):
            actor_note += " (PETTY CASH initials)"
        parts.append(actor_note)
    if confidence:
        parts.append(f"confidence: {confidence}")
    return " | ".join(parts)


def _backlog_note(
    *,
    case_id: str,
    detected_at: str,
    entry: Dict[str, Any],
    manifest: Optional[Dict[str, Any]] = None,
) -> str:
    finding = str(entry.get("finding") or "").strip()
    label = _finding_label(finding)
    date = str(entry.get("posted_date") or "").strip()
    company = str(entry.get("company_id") or "").strip().upper()
    desc = str(entry.get("description") or "").strip()
    amount_cents = int(entry.get("amount_cents") or 0)
    kylo_post = str(entry.get("kylo_post") or "").strip()
    detail = str(entry.get("detail") or "").strip()
    pair_row = entry.get("pair_row")

    parts = [
        "KYLO-AUDIT-SYSTEM",
        case_id,
        label,
        f"{date} {company} {desc} {_fmt_amount(amount_cents)}",
    ]
    if kylo_post:
        parts.append(kylo_post)
    if pair_row:
        parts.append(f"paired row {pair_row}")
    if detail:
        parts.append(detail)
    if manifest is not None:
        timing = _fmt_estimated_edit(_resolve_estimated_edit(entry, manifest))
        if timing:
            parts.append(timing)
    parts.extend([f"detected {detected_at}", "automated forensic audit", "NOT manual user entry"])
    return " | ".join(parts)[:500]


def _anomalies_for_finding(finding: str) -> List[str]:
    base = ["SYSTEM_BACKLOG", "FALSE_EDIT", "SYSTEM_DETECTED"]
    if finding == "row_insertion":
        return base + ["ROW_INSERTED", "LATE_ARRIVAL", "SYSTEM_DETECTED_ROW_INSERTION"]
    if finding == "amount_changed":
        return base + ["AMOUNT_CHANGED", "SYSTEM_DETECTED_AMOUNT_CHANGE"]
    if finding == "false_payroll_transaction":
        return base + [
            "FALSE_PAYROLL",
            "INFLATED_PAYROLL_APPEARANCE",
            "ROW_INSERTED",
            "AMOUNT_CHANGED",
            "SYSTEM_DETECTED_FALSE_PAYROLL",
        ]
    return base + ["AMOUNT_REVISION"]


def events_from_manifest(manifest: Dict[str, Any], *, applied_at: Optional[str] = None) -> List[ChangeEvent]:
    ts = applied_at or str(manifest.get("detected_at") or _utc_now_iso())
    intake = manifest.get("intake") or {}
    sid = str(intake.get("spreadsheet_id") or "").strip()
    tab = str(intake.get("tab") or "TRANSACTIONS").strip()
    events: List[ChangeEvent] = []
    for entry in manifest.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        sheet_row = int(entry.get("sheet_row") or 0)
        if sheet_row < 1:
            continue
        row0 = sheet_row - 1
        rk = make_row_key(sid, tab, row0)
        finding = str(entry.get("finding") or "").strip()
        amount_cents = int(entry.get("amount_cents") or 0)
        desc = str(entry.get("description") or "")
        company = str(entry.get("company_id") or "").strip().upper()
        pdate = str(entry.get("posted_date") or "")
        anomalies = _anomalies_for_finding(finding)

        if finding == "row_insertion":
            events.append(
                ChangeEvent(
                    ts=ts,
                    event="ROW_INSERTED",
                    row_key=rk,
                    source_spreadsheet_id=sid,
                    source_tab=tab,
                    sheet_row=sheet_row,
                    company_id=company,
                    changed_field="row",
                    before="",
                    after=f"date={pdate} amount={amount_cents/100:.2f} source={desc}",
                    anomalies=anomalies,
                    posted_date=pdate,
                    description=desc,
                    amount_cents=amount_cents,
                )
            )
        elif finding == "false_payroll_transaction":
            events.append(
                ChangeEvent(
                    ts=ts,
                    event="ANOMALY",
                    row_key=rk,
                    source_spreadsheet_id=sid,
                    source_tab=tab,
                    sheet_row=sheet_row,
                    company_id=company,
                    changed_field="payroll",
                    before="LEGITIMATE_PAYROLL",
                    after=f"FALSE_PAYROLL_PAIR amount={amount_cents/100:.2f} source={desc}",
                    anomalies=anomalies,
                    posted_date=pdate,
                    description=desc,
                    amount_cents=amount_cents,
                )
            )
        else:
            events.append(
                ChangeEvent(
                    ts=ts,
                    event="ROW_CHANGED",
                    row_key=rk,
                    source_spreadsheet_id=sid,
                    source_tab=tab,
                    sheet_row=sheet_row,
                    company_id=company,
                    changed_field="amount",
                    before="PRIOR_LOG_AMOUNT",
                    after=f"{amount_cents/100:.2f}",
                    anomalies=anomalies,
                    posted_date=pdate,
                    description=desc,
                    amount_cents=amount_cents,
                )
            )
    return events


def write_backlog_notes(
    service,
    manifest: Dict[str, Any],
    *,
    note_column: str = "G",
) -> int:
    intake = manifest.get("intake") or {}
    sid = str(intake.get("spreadsheet_id") or "").strip()
    tab = str(intake.get("tab") or "TRANSACTIONS").strip()
    case_id = str(manifest.get("case_id") or "BACKLOG")
    detected_at = str(manifest.get("detected_at") or _utc_now_iso())
    tab_q = "'" + tab.replace("'", "''") + "'" if re.search(r"[^A-Za-z0-9_]", tab) else tab

    batch: List[dict] = []
    for entry in manifest.get("entries") or []:
        if not isinstance(entry, dict) or not entry.get("sheet_row"):
            continue
        sheet_row = int(entry["sheet_row"])
        note = _backlog_note(case_id=case_id, detected_at=detected_at, entry=entry, manifest=manifest)
        batch.append({"range": f"{tab_q}!{note_column}{sheet_row}", "values": [[note]]})

    if not batch or not sid:
        return 0
    google_api_execute(
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=sid,
            body={"valueInputOption": "USER_ENTERED", "data": batch},
        ),
        label="backlog:notes_batch",
    )
    print(f"[BACKLOG] Wrote {len(batch)} Kylo system audit note(s) to {tab} column {note_column}")
    return len(batch)


def _load_posted_notes_csv(path: Path) -> Dict[int, str]:
    out: Dict[int, str] = {}
    if not path.exists():
        return out
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                sheet_row = int(row.get("sheet_row") or row.get("row") or 0)
            except (TypeError, ValueError):
                continue
            note = str(row.get("note") or "").strip()
            if sheet_row > 0 and note:
                out[sheet_row] = note
    return out


def restore_kylo_posted_notes(
    service,
    *,
    spreadsheet_id: str,
    tab: str,
    rows: Set[int],
    notes_by_row: Dict[int, str],
    note_column: str = "G",
) -> int:
    if not rows or not spreadsheet_id:
        return 0
    tab_q = "'" + tab.replace("'", "''") + "'" if re.search(r"[^A-Za-z0-9_]", tab) else tab
    batch: List[dict] = []
    for row in sorted(rows):
        note = notes_by_row.get(row)
        if not note:
            continue
        batch.append({"range": f"{tab_q}!{note_column}{row}", "values": [[note]]})
    if not batch:
        return 0
    google_api_execute(
        service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "USER_ENTERED", "data": batch},
        ),
        label="backlog:restore_posted_notes",
    )
    print(f"[BACKLOG] Restored {len(batch)} original Kylo posting note(s)")
    return len(batch)


def apply_audit_backlog(
    manifest_path: Path,
    *,
    instance_id: str = "KYLO_2026",
    force: bool = False,
    apply_highlights: bool = True,
    write_notes: bool = True,
    service_account_path: Optional[str] = None,
) -> Dict[str, Any]:
    manifest = _load_yaml(manifest_path)
    applied_path = Path(".kylo") / "instances" / instance_id / "state" / "audit_backlog_applied.json"
    case_id = str(manifest.get("case_id") or "BACKLOG")
    if applied_path.exists() and not force:
        try:
            prev = json.loads(applied_path.read_text(encoding="utf-8"))
            if prev.get("manifest_case_id") == case_id:
                print(f"[BACKLOG] Case {case_id} already applied (use --force to re-apply highlights/notes)")
                return prev
        except Exception:
            pass

    prev_rows: Set[int] = set()
    if applied_path.exists():
        try:
            prev_data = json.loads(applied_path.read_text(encoding="utf-8"))
            prev_rows = {int(r) for r in (prev_data.get("rows") or {})}
        except Exception:
            pass

    applied_at = _utc_now_iso()
    events = events_from_manifest(manifest, applied_at=applied_at)
    intake = manifest.get("intake") or {}
    sid = str(intake.get("spreadsheet_id") or "").strip()
    tab = str(intake.get("tab") or "TRANSACTIONS").strip()
    note_col = str(intake.get("note_column") or "G")
    new_rows = {int(e.get("sheet_row")) for e in (manifest.get("entries") or []) if e.get("sheet_row")}

    from services.common.config_loader import load_config
    from services.sheets.poster import _get_service

    cfg = load_config()
    sa = service_account_path or cfg.get("google.service_account_json_path")
    if sa and Path(str(sa)).exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(sa)
    service = _get_service()

    rows_to_restore = prev_rows - new_rows
    notes_restored = 0
    highlights_cleared = 0
    if rows_to_restore:
        csv_rel = str(manifest.get("restore_posted_notes_csv") or "tools/debug/_2026_txn_posted_backlog.csv")
        csv_path = Path(csv_rel)
        if not csv_path.is_absolute():
            repo_root = manifest_path.resolve().parent.parent.parent
            csv_path = repo_root / csv_rel
        notes_by_row = _load_posted_notes_csv(csv_path)
        if write_notes:
            notes_restored = restore_kylo_posted_notes(
                service,
                spreadsheet_id=sid,
                tab=tab,
                rows=rows_to_restore,
                notes_by_row=notes_by_row,
                note_column=note_col,
            )
        if apply_highlights:
            highlights_cleared = clear_row_highlights(service, sid, tab, sorted(rows_to_restore), cfg)

    highlights_applied = 0
    notes_written = 0
    if apply_highlights and events:
        highlights_applied = apply_audit_highlights(service, events, cfg)
    if write_notes and manifest.get("entries"):
        notes_written = write_backlog_notes(service, manifest, note_column=note_col)

    append_audit_log(audit_log_path(instance_id), events, instance_id=instance_id)
    append_audit_jsonl(audit_jsonl_path(instance_id), events, instance_id=instance_id)
    with audit_log_path(instance_id).open("a", encoding="utf-8") as f:
        f.write(
            f"{applied_at} | {instance_id} | KYLO_FORENSIC_AUDIT_SYSTEM | BACKLOG_APPLIED | "
            f"case={case_id} | rows={len(manifest.get('entries') or [])} | "
            f"restored={notes_restored} | attribution=automated_system_not_human\n"
        )

    registry = load_row_registry(row_registry_path(instance_id))
    for entry in manifest.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        sheet_row = int(entry.get("sheet_row") or 0)
        row0 = sheet_row - 1
        rk = make_row_key(sid, tab, row0)
        registry[rk] = RowRecord(
            row_key=rk,
            source_spreadsheet_id=sid,
            source_tab=tab,
            row_index_0based=row0,
            company_id=str(entry.get("company_id") or "").strip().upper(),
            posted_date=str(entry.get("posted_date") or ""),
            description=str(entry.get("description") or ""),
            amount_cents=int(entry.get("amount_cents") or 0),
            posted_flag=True,
            first_seen_at=str(manifest.get("detected_at") or applied_at),
            content_fp=f"{entry.get('posted_date')}|{entry.get('company_id')}|{entry.get('amount_cents')}|{entry.get('description')}",
        )
    save_row_registry(row_registry_path(instance_id), registry)

    snap_stamp = f"BACKLOG-{case_id}-{applied_at.replace(':', '-').replace('.', '-')[:19]}"
    snap_dir = snapshots_root(instance_id) / snap_stamp
    snap_dir.mkdir(parents=True, exist_ok=True)
    timeline_path = manifest_path.resolve().parent / "kylo_2026_false_edit_timeline.yaml"
    backlog_payload = {
        "ts": applied_at,
        "detector": "KYLO_FORENSIC_AUDIT_SYSTEM",
        "case_id": case_id,
        "summary": manifest.get("summary"),
        "forensic_lower_bound": manifest.get("forensic_lower_bound"),
        "row_groups": manifest.get("row_groups"),
        "estimated_edit_timeline_path": str(timeline_path) if timeline_path.exists() else None,
        "events": [e.to_dict() for e in events],
        "manifest_path": str(manifest_path.resolve()),
        "attribution": manifest.get("attribution"),
    }
    (snap_dir / "backlog.json").write_text(json.dumps(backlog_payload, indent=2) + "\n", encoding="utf-8")
    save_tick_snapshot(
        instance_id,
        csv_by_key={},
        row_registry=registry,
        events=events,
        meta={"backlog_case": case_id, "backlog_rows": len(manifest.get("entries") or [])},
    )

    detected_at = str(manifest.get("detected_at") or applied_at)
    rows_meta = {}
    for e in (manifest.get("entries") or []):
        if not isinstance(e, dict):
            continue
        estimated = _resolve_estimated_edit(e, manifest)
        rows_meta[str(e.get("sheet_row"))] = {
            **e,
            "estimated_edit": estimated,
            "note": _backlog_note(
                case_id=case_id,
                detected_at=detected_at,
                entry=e,
                manifest=manifest,
            ),
        }
    result = {
        "applied_at": applied_at,
        "detector": "KYLO_FORENSIC_AUDIT_SYSTEM",
        "manifest_case_id": case_id,
        "manifest_path": str(manifest_path.resolve()),
        "instance_id": instance_id,
        "summary": manifest.get("summary"),
        "forensic_lower_bound": manifest.get("forensic_lower_bound"),
        "estimated_edit_timeline_path": str(timeline_path) if timeline_path.exists() else None,
        "row_groups": manifest.get("row_groups"),
        "event_count": len(events),
        "events": [e.to_dict() for e in events],
        "rows": rows_meta,
        "highlights_applied": highlights_applied,
        "highlights_cleared": highlights_cleared,
        "notes_written": notes_written,
        "notes_restored": notes_restored,
        "snapshot_dir": str(snap_dir),
        "attribution": manifest.get("attribution"),
    }
    applied_path.parent.mkdir(parents=True, exist_ok=True)
    applied_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"[BACKLOG] Applied case {case_id}: {len(manifest.get('entries') or [])} rows, "
        f"{highlights_applied} highlights, {notes_written} notes, {notes_restored} restored"
    )
    return result


__all__ = ["apply_audit_backlog", "events_from_manifest"]
