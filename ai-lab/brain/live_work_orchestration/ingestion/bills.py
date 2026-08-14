"""Read-only bills ingestion for live-work planning."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from brain.prepared_context.schema import now_iso


@dataclass
class BillRecord:
    name: str
    due_date: str = ""
    amount: float | None = None
    currency: str = "USD"
    status: str = "unknown"
    timing_status: str = "unknown"
    days_until_due: int | None = None
    source: str = "manual_bills"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _ingestion_dir() -> Path:
    from brain.live_work_orchestration.builders import live_work_dir

    d = live_work_dir() / "ingestion"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _parse_due_date(raw: Any) -> date | None:
    text = str(raw or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def evaluate_bill_status(row: dict[str, Any] | BillRecord) -> dict[str, Any]:
    data = row.to_dict() if isinstance(row, BillRecord) else dict(row or {})
    due = _parse_due_date(data.get("due_date"))
    today = datetime.now(timezone.utc).date()
    days = (due - today).days if due else None
    status = str(data.get("status") or "").strip().lower()
    if status in ("paid", "cancelled", "skipped"):
        timing = "closed"
    elif days is None:
        status = status or "unknown"
        timing = "unknown"
    elif days < 0:
        status = "overdue"
        timing = "at_risk"
    elif days <= 3:
        status = status or "due_soon"
        timing = "at_risk"
    elif days <= 14:
        status = status or "upcoming"
        timing = "upcoming"
    else:
        status = status or "scheduled"
        timing = "scheduled"
    data["status"] = status
    data["timing_status"] = timing
    data["days_until_due"] = days
    return data


def validate_bill_record(row: dict[str, Any] | BillRecord) -> tuple[bool, list[str]]:
    data = row.to_dict() if isinstance(row, BillRecord) else dict(row or {})
    errors: list[str] = []
    if not str(data.get("name") or "").strip():
        errors.append("missing name")
    if data.get("due_date") and _parse_due_date(data.get("due_date")) is None:
        errors.append("invalid due_date")
    amount = data.get("amount")
    if amount not in (None, ""):
        try:
            float(amount)
        except (TypeError, ValueError):
            errors.append("invalid amount")
    return (len(errors) == 0, errors)


def build_bill_clarification(row: dict[str, Any] | BillRecord) -> dict[str, Any] | None:
    ok, errors = validate_bill_record(row)
    if ok:
        return None
    data = row.to_dict() if isinstance(row, BillRecord) else dict(row or {})
    return {
        "source": "bills_ingestion",
        "reason": "bill_record_needs_clarification",
        "message": f"Bill record needs clarification: {', '.join(errors)}",
        "evidence": [str(data.get("name") or "unnamed_bill")],
    }


def _manual_bills_path() -> Path:
    env = (os.environ.get("AI_LAB_MANUAL_BILLS_JSON") or "").strip()
    if env:
        return Path(env)
    from brain.live_work_orchestration.builders import live_work_dir

    return live_work_dir() / "manual_bills.json"


def load_manual_bills(path: str | Path | None = None) -> list[dict[str, Any]]:
    p = Path(path) if path else _manual_bills_path()
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = raw.get("bills") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            out.append(evaluate_bill_status(row))
    return out


def summarize_bills_for_planning(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    rows = []
    if isinstance(snapshot, dict):
        data = snapshot.get("data")
        if isinstance(data, list):
            rows = [r for r in data if isinstance(r, dict)]
        elif isinstance(data, dict):
            rows = [r for r in data.get("bills", []) if isinstance(r, dict)]
    normalized = [evaluate_bill_status(r) for r in rows]
    overdue = [r for r in normalized if r.get("status") == "overdue"]
    upcoming = [r for r in normalized if r.get("timing_status") in ("upcoming", "at_risk")]
    high_risk = [r for r in normalized if r.get("timing_status") == "at_risk"]
    warnings = []
    if overdue:
        warnings.append(f"{len(overdue)} bill(s) overdue")
    if high_risk:
        warnings.append(f"{len(high_risk)} bill(s) due soon or at risk")
    clarifications = [c for c in (build_bill_clarification(r) for r in normalized) if c]
    return {
        "upcoming": upcoming,
        "overdue": overdue,
        "high_risk": high_risk,
        "warnings": warnings,
        "clarifications": clarifications,
    }


def build_bills_snapshot() -> dict[str, Any]:
    rows = load_manual_bills()
    summary = summarize_bills_for_planning({"data": rows})
    payload = {
        "snapshot_type": "bills_snapshot",
        "generated_at": now_iso(),
        "stale": False,
        "confidence": 0.75 if rows else 0.35,
        "source_files_or_tools": [str(_manual_bills_path())],
        "missing_sources": [] if rows else ["manual_bills_json"],
        "errors": [],
        "data": rows,
        "summary_short": f"Bills snapshot: {len(rows)} row(s), {len(summary['overdue'])} overdue",
        "summary_detailed": "Read-only bills snapshot from local manual_bills.json when present.",
        "evidence_items": [],
        "suggested_questions": [],
    }
    (_ingestion_dir() / "bills_snapshot.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload
