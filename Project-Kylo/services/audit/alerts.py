from __future__ import annotations

import os
from typing import Any, Dict, List, Set

from services.audit.row_model import ChangeEvent

DEFAULT_ALERT_ANOMALIES: Set[str] = {
    "AMOUNT_REVISION",
    "ROW_INSERTED",
    "FALSE_PAYROLL",
    "FROM_BANK_PAIR",
    "INFLATED_PAYROLL_APPEARANCE",
    "POSTED_FLAG_TOGGLED",
    "KYLO_POSTED_VARIANCE",
    "LATE_ARRIVAL",
    "NEW_ALREADY_POSTED",
}


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


def _should_alert(event: ChangeEvent, alert_anomalies: Set[str]) -> bool:
    if not event.anomalies:
        return event.event in ("ROW_INSERTED", "ROW_CHANGED", "ANOMALY")
    return bool(alert_anomalies.intersection(event.anomalies))


def emit_audit_alerts(
    events: List[ChangeEvent],
    *,
    instance_id: str,
    cfg: Any = None,
) -> int:
    """Send audit anomaly events to telemetry webhook (n8n/Slack/email)."""
    block = _cfg_get(cfg, "audit.alerts") or {}
    if isinstance(block, dict) and block.get("enabled") is False:
        return 0
    raw_off = (os.environ.get("KYLO_AUDIT_ALERTS") or "").strip().lower()
    if raw_off in ("0", "false", "no", "off"):
        return 0

    configured = block.get("anomalies") if isinstance(block, dict) else None
    alert_set = set(str(x) for x in configured) if configured else set(DEFAULT_ALERT_ANOMALIES)

    try:
        from telemetry.emitter import emit, start_trace
    except ImportError:
        return 0

    trace_id = start_trace("audit", instance_id or "kylo")
    sent = 0
    for ev in events:
        if not _should_alert(ev, alert_set):
            continue
        level = "warning" if ev.anomalies else "info"
        if "FALSE_PAYROLL" in ev.anomalies or "INFLATED_PAYROLL_APPEARANCE" in ev.anomalies:
            level = "error"
        emit(
            "audit",
            trace_id,
            "anomaly_detected",
            {
                "instance_id": instance_id,
                "sheet_row": ev.sheet_row,
                "company_id": ev.company_id,
                "source_tab": ev.source_tab,
                "source_spreadsheet_id": ev.source_spreadsheet_id,
                "event": ev.event,
                "changed_field": ev.changed_field,
                "before": ev.before,
                "after": ev.after,
                "anomalies": ev.anomalies,
                "description": ev.description,
                "amount_cents": ev.amount_cents,
                "business_line_uid": ev.business_line_uid,
            },
            level=level,
        )
        sent += 1
    if sent:
        print(f"[AUDIT] Emitted {sent} alert(s) via telemetry")
    return sent


__all__ = ["emit_audit_alerts"]
