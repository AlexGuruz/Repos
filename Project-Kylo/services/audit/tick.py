from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from services.audit.alerts import emit_audit_alerts
from services.audit.highlights import apply_audit_highlights
from services.audit.intake_loader import load_all_intake
from services.audit.logger import append_audit_jsonl, append_audit_log
from services.audit.notes import write_audit_notes
from services.audit.pair_rules import detect_from_bank_payroll_pairs, detect_kylo_posted_amount_variance
from services.audit.paths import (
    audit_jsonl_path,
    audit_log_path,
    business_line_registry_path,
    revision_state_path,
    row_registry_path,
)
from services.audit.revisions import poll_spreadsheet_revisions
from services.audit.row_model import ChangeEvent, RowRecord
from services.audit.sheet_diff import diff_registries, merge_registry
from services.audit.snapshot import load_row_registry, save_row_registry, save_tick_snapshot
from services.audit.txn_diff import (
    build_business_line_registry,
    diff_business_line_registries,
    merge_business_line_registry,
)
from services.common.instance import default_posting_state_path, default_watch_state_path
from services.sheets.poster import _get_service


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _cfg_get(cfg: Any, dotted: str, default: Any = None) -> Any:
    if cfg is None:
        return default
    if hasattr(cfg, "get"):
        try:
            v = cfg.get(dotted, None)
            if v is not None:
                return v
        except TypeError:
            pass
    return default


def _sheets_writes_blocked() -> bool:
    return os.environ.get("KYLO_SHEETS_DRY_RUN", "").strip().lower() in ("1", "true", "yes", "y") or os.environ.get(
        "KYLO_READ_ONLY", ""
    ).strip().lower() in ("1", "true", "yes", "y")


def _dedupe_events(events: List[ChangeEvent]) -> List[ChangeEvent]:
    seen: Set[tuple] = set()
    out: List[ChangeEvent] = []
    for ev in events:
        sig = (ev.row_key, ev.event, ev.changed_field, ev.before, ev.after, tuple(ev.anomalies))
        if sig in seen:
            continue
        seen.add(sig)
        out.append(ev)
    return out


def _source_key(record: RowRecord) -> str:
    return f"{record.source_spreadsheet_id}|{record.source_tab.upper()}"


def _loaded_source_key(raw: str) -> str:
    sid, sep, tab = str(raw or "").strip().partition("|")
    if not sep:
        return str(raw or "").strip()
    return f"{sid}|{tab.upper()}"


def _only_loaded_sources(
    registry: Dict[str, RowRecord], loaded_sources: Set[str]
) -> Dict[str, RowRecord]:
    return {k: v for k, v in registry.items() if _source_key(v) in loaded_sources}


def _preserve_unloaded_sources(
    registry: Dict[str, RowRecord], loaded_sources: Set[str]
) -> Dict[str, RowRecord]:
    return {k: v for k, v in registry.items() if _source_key(v) not in loaded_sources}


def audit_enabled(cfg) -> bool:
    raw_off = (os.environ.get("KYLO_AUDIT") or "").strip().lower()
    if raw_off in ("0", "false", "no", "n", "off"):
        return False
    mode = (os.environ.get("KYLO_RUNTIME_MODE") or _cfg_get(cfg, "runtime.mode", "audit") or "audit").strip().lower()
    if mode == "post":
        block = _cfg_get(cfg, "audit") or {}
        return bool(block.get("enabled", True)) if isinstance(block, dict) else True
    return True


def is_audit_mode(cfg) -> bool:
    if os.environ.get("KYLO_ALLOW_POST", "").strip().lower() in ("1", "true", "yes", "y"):
        return False
    mode = (os.environ.get("KYLO_RUNTIME_MODE") or _cfg_get(cfg, "runtime.mode", "audit") or "audit").strip().lower()
    return mode != "post"


def run_audit_tick(
    cfg,
    companies: List[str],
    *,
    instance_id: str,
    watch_state_path: Optional[str] = None,
    posting_state_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Run one forensic audit cycle: load intake, diff, log, snapshot, highlight, alert."""
    ts = _utc_now_iso()
    summary: Dict[str, Any] = {
        "ts": ts,
        "instance_id": instance_id,
        "companies": companies,
        "events": 0,
        "alerts_sent": 0,
        "highlights_applied": 0,
        "notes_written": 0,
        "snapshot_dir": "",
        "baseline": False,
    }
    if not audit_enabled(cfg):
        summary["skipped"] = "audit_disabled"
        return summary

    audit_block = _cfg_get(cfg, "audit") or {}
    if not isinstance(audit_block, dict):
        audit_block = {}

    reg_path = row_registry_path(instance_id)
    bl_path = business_line_registry_path(instance_id)
    previous = load_row_registry(reg_path)
    previous_bl = load_row_registry(bl_path)

    try:
        txns, csv_by_key = load_all_intake(cfg, companies)
    except Exception as e:
        summary["error"] = f"intake_load_failed: {e}"
        print(f"[AUDIT] ERROR loading intake: {e}")
        return summary
    loaded_sources = {_loaded_source_key(str(k)) for k in csv_by_key.keys() if str(k).strip()}
    if not loaded_sources:
        summary["error"] = "intake_load_failed: no source tabs loaded"
        print("[AUDIT] ERROR loading intake: no source tabs loaded")
        return summary

    current: Dict[str, RowRecord] = {}
    for txn in txns:
        rec = RowRecord.from_txn(txn, first_seen_at=ts)
        if rec:
            prev = previous.get(rec.row_key)
            if prev:
                rec.kylo_posted_at = prev.kylo_posted_at
                rec.kylo_posted_amount_cents = prev.kylo_posted_amount_cents
            current[rec.row_key] = rec

    current_list = list(current.values())
    current_bl = build_business_line_registry(current_list)
    previous_loaded = _only_loaded_sources(previous, loaded_sources)
    previous_unloaded = _preserve_unloaded_sources(previous, loaded_sources)
    previous_bl_loaded = _only_loaded_sources(previous_bl, loaded_sources)
    previous_bl_unloaded = _preserve_unloaded_sources(previous_bl, loaded_sources)
    late_days = int(audit_block.get("late_arrival_min_posted_days", 14) or 14)

    events: List[ChangeEvent] = []
    if previous_loaded:
        events.extend(diff_registries(previous_loaded, current, ts=ts, late_arrival_min_posted_days=late_days))
    else:
        summary["baseline"] = True
        print(f"[AUDIT] Baseline registry for loaded sources: {len(current)} rows (no diff on first tick)")

    if previous_bl_loaded:
        events.extend(diff_business_line_registries(previous_bl_loaded, current_bl, ts=ts))

    pair_block = audit_block.get("pair_rules") or {}
    if not isinstance(pair_block, dict) or pair_block.get("enabled", True):
        max_dist = int(pair_block.get("max_pair_distance_rows", 3) or 3) if isinstance(pair_block, dict) else 3
        events.extend(detect_from_bank_payroll_pairs(current_list, ts=ts, max_pair_distance=max_dist))

    events.extend(detect_kylo_posted_amount_variance(current_list, ts=ts))

    rev_block = audit_block.get("revision_poll") or {}
    if isinstance(rev_block, dict) and rev_block.get("enabled", False):
        sids = sorted({r.source_spreadsheet_id for r in current_list if r.source_spreadsheet_id})
        events.extend(
            poll_spreadsheet_revisions(
                spreadsheet_ids=sids,
                revision_state_path=revision_state_path(instance_id),
            )
        )

    events = _dedupe_events(events)

    merged = previous_unloaded
    merged.update(merge_registry(previous_loaded, current, ts=ts))
    merged_bl = previous_bl_unloaded
    merged_bl.update(merge_business_line_registry(previous_bl_loaded, current_bl, ts=ts))
    save_row_registry(reg_path, merged)
    save_row_registry(bl_path, merged_bl)

    log_path = audit_log_path(instance_id)
    jsonl_path = audit_jsonl_path(instance_id)
    if events:
        append_audit_log(log_path, events, instance_id=instance_id)
        append_audit_jsonl(jsonl_path, events, instance_id=instance_id)
        for ev in events:
            print(f"[AUDIT] {ev.human_line(instance_id)}")
        summary["alerts_sent"] = emit_audit_alerts(events, instance_id=instance_id, cfg=cfg)

    iid = instance_id
    w_path = Path(watch_state_path) if watch_state_path else default_watch_state_path(iid)
    p_path = Path(posting_state_path) if posting_state_path else default_posting_state_path(iid)

    snap_dir = save_tick_snapshot(
        instance_id,
        csv_by_key=csv_by_key,
        row_registry=merged,
        events=events,
        meta={
            "companies": companies,
            "row_count": len(current),
            "business_line_count": len(current_bl),
            "csv_tabs": sorted(csv_by_key.keys()),
            "preserved_unloaded_rows": len(previous_unloaded),
            "baseline": summary["baseline"],
        },
        watch_state_path=w_path if w_path.exists() else None,
        posting_state_path=p_path if p_path.exists() else None,
    )
    summary["snapshot_dir"] = str(snap_dir)
    summary["events"] = len(events)

    write_notes = bool(audit_block.get("write_notes", True))
    apply_hl = bool(audit_block.get("apply_highlights", True))
    if events and (write_notes or apply_hl) and not _sheets_writes_blocked():
        try:
            service = _get_service()
        except Exception as e:
            print(f"[AUDIT] WARN: Sheets service unavailable for highlights: {e}")
            service = None
        if service is not None:
            if apply_hl:
                try:
                    summary["highlights_applied"] = apply_audit_highlights(service, events, cfg)
                except Exception as e:
                    print(f"[AUDIT] WARN: highlights failed: {e}")
            if write_notes:
                note_col = str(audit_block.get("note_column", "G") or "G")
                try:
                    summary["notes_written"] = write_audit_notes(
                        service, events, note_column=note_col, case_id="LIVE-AUDIT"
                    )
                except Exception as e:
                    print(f"[AUDIT] WARN: notes failed: {e}")
    elif events and (write_notes or apply_hl) and _sheets_writes_blocked():
        print("[AUDIT] Skipping sheet highlights/notes (dry-run or read-only)")

    print(
        f"[AUDIT] tick complete rows={len(current)} events={len(events)} "
        f"alerts={summary.get('alerts_sent', 0)} snapshot={snap_dir.name}"
    )
    return summary


__all__ = ["audit_enabled", "is_audit_mode", "run_audit_tick"]
