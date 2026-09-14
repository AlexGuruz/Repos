from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from brain.prepared_context.schema import now_iso


@dataclass
class BillRecord:
    name: str
    due_date: str | None = None
    amount: float | None = None
    currency: str = "USD"
    status: str = "open"
    source: str = "manual"
    notes: str = ""


def _live_work_dir() -> Path:
    root = Path(__file__).resolve().parents[3]
    d = root / "state" / "live_work_orchestration"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _parse_due_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def validate_bill_record(row: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not str(row.get("name") or "").strip():
        errors.append("missing_name")
    if _parse_due_date(row.get("due_date")) is None:
        errors.append("missing_or_invalid_due_date")
    amount = row.get("amount")
    if amount is not None:
        try:
            if float(amount) < 0:
                errors.append("negative_amount")
        except (TypeError, ValueError):
            errors.append("invalid_amount")
    return not errors, errors


def evaluate_bill_status(row: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    out = dict(row)
    due = _parse_due_date(out.get("due_date"))
    today = today or datetime.now(timezone.utc).date()
    days_until_due = (due - today).days if due else None
    raw_status = str(out.get("status") or "open").strip().lower()
    paid = raw_status in {"paid", "done", "closed"}

    if paid:
        status = "paid"
        timing_status = "settled"
    elif days_until_due is None:
        status = "unknown"
        timing_status = "needs_due_date"
    elif days_until_due < 0:
        status = "overdue"
        timing_status = "at_risk"
    elif days_until_due <= 7:
        status = "open"
        timing_status = "at_risk"
    elif days_until_due <= 14:
        status = "open"
        timing_status = "upcoming"
    else:
        status = "open"
        timing_status = "future"

    out["status"] = status
    out["timing_status"] = timing_status
    out["days_until_due"] = days_until_due
    return out


def build_bill_clarification(row: dict[str, Any]) -> dict[str, Any] | None:
    ok, errors = validate_bill_record(row)
    if ok:
        return None
    name = str(row.get("name") or "unknown bill")
    return {
        "message": f"Confirm bill details for {name}: {', '.join(errors)}.",
        "reason": "bill_details_missing",
        "source": "bills_ingestion",
        "target_list": "Agent Bills",
        "evidence": errors,
    }


def load_manual_bills(path: Path | None = None) -> list[dict[str, Any]]:
    source = path or (_live_work_dir() / "ingestion" / "manual_bills.json")
    if not source.is_file():
        return []
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = raw.get("bills") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, BillRecord):
            out.append(asdict(row))
        elif isinstance(row, dict):
            out.append(dict(row))
    return out


def summarize_bills_for_planning(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    rows = list((snapshot or {}).get("data") or [])
    rows = [r for r in rows if isinstance(r, dict)]
    overdue = [r for r in rows if r.get("status") == "overdue"]
    upcoming = [r for r in rows if r.get("timing_status") == "upcoming"]
    high_risk = [r for r in rows if r.get("timing_status") == "at_risk"]
    warnings = [
        f"{r.get('name', 'unknown bill')} is {r.get('timing_status')}"
        for r in rows
        if r.get("timing_status") in {"at_risk", "needs_due_date"}
    ]
    clarifications = [c for c in (build_bill_clarification(r) for r in rows) if c]
    return {
        "upcoming": upcoming,
        "overdue": overdue,
        "high_risk": high_risk,
        "warnings": warnings,
        "clarifications": clarifications,
        "total_count": len(rows),
    }


def build_bills_snapshot() -> dict[str, Any]:
    rows = [evaluate_bill_status(r) for r in load_manual_bills()]
    summary = summarize_bills_for_planning({"data": rows})
    payload = {
        "snapshot_type": "bills_snapshot",
        "generated_at": now_iso(),
        "stale": False,
        "confidence": 0.7 if rows else 0.45,
        "source_files_or_tools": ["state/live_work_orchestration/ingestion/manual_bills.json"],
        "missing_sources": [] if rows else ["manual_bills"],
        "errors": [],
        "data": rows,
        "summary_short": f"Bills: {len(rows)} row(s); {len(summary['overdue'])} overdue",
        "summary_detailed": "Manual financial-obligation snapshot only; no payment or bank actions.",
        "evidence_items": [],
        "suggested_questions": [],
    }
    out = _live_work_dir() / "ingestion" / "bills_snapshot.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return payload


__all__ = [
    "BillRecord",
    "build_bill_clarification",
    "build_bills_snapshot",
    "evaluate_bill_status",
    "load_manual_bills",
    "summarize_bills_for_planning",
    "validate_bill_record",
]
