from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
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
    status: str = "unknown"
    timing_status: str = "unknown"
    days_until_due: int | None = None
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _parse_due_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def evaluate_bill_status(row: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    out = dict(row)
    due = _parse_due_date(out.get("due_date"))
    if due is None:
        out.setdefault("status", "unknown")
        out.setdefault("timing_status", "unknown")
        out.setdefault("days_until_due", None)
        return out

    days = (due - today).days
    out["days_until_due"] = days
    paid = str(out.get("status") or "").lower() in {"paid", "done", "cancelled"}
    if paid:
        out["timing_status"] = "settled"
    elif days < 0:
        out["status"] = "overdue"
        out["timing_status"] = "at_risk"
    elif days <= 7:
        out.setdefault("status", "open")
        out["timing_status"] = "at_risk"
    elif days <= 30:
        out.setdefault("status", "open")
        out["timing_status"] = "upcoming"
    else:
        out.setdefault("status", "open")
        out["timing_status"] = "future"
    return out


def validate_bill_record(row: dict[str, Any]) -> BillRecord:
    evaluated = evaluate_bill_status(row)
    name = str(evaluated.get("name") or evaluated.get("title") or "Unnamed bill").strip()
    amount_raw = evaluated.get("amount")
    amount: float | None
    try:
        amount = float(amount_raw) if amount_raw not in (None, "") else None
    except (TypeError, ValueError):
        amount = None
    evidence = evaluated.get("evidence")
    return BillRecord(
        name=name,
        due_date=str(evaluated.get("due_date")) if evaluated.get("due_date") else None,
        amount=amount,
        currency=str(evaluated.get("currency") or "USD"),
        status=str(evaluated.get("status") or "unknown"),
        timing_status=str(evaluated.get("timing_status") or "unknown"),
        days_until_due=evaluated.get("days_until_due") if isinstance(evaluated.get("days_until_due"), int) else None,
        evidence=list(evidence) if isinstance(evidence, list) else [],
    )


def _manual_bills_path() -> Path:
    configured = os.environ.get("AI_LAB_MANUAL_BILLS_PATH")
    if configured:
        return Path(configured)
    from brain.live_work_orchestration.builders import live_work_dir

    return live_work_dir() / "ingestion" / "manual_bills.json"


def load_manual_bills(path: str | Path | None = None) -> list[BillRecord]:
    p = Path(path) if path is not None else _manual_bills_path()
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = raw.get("bills") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return []
    out: list[BillRecord] = []
    for item in rows:
        if isinstance(item, dict):
            out.append(validate_bill_record(item))
    return out


def _rows_from_snapshot(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(snapshot, dict):
        return []
    data = snapshot.get("data")
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        rows = data.get("bills") or data.get("rows") or []
        if isinstance(rows, list):
            return [x for x in rows if isinstance(x, dict)]
    return []


def build_bill_clarification(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "bill_clarification",
        "name": row.get("name") or "Unnamed bill",
        "reason": "missing_due_date_or_amount",
        "message": f"Confirm due date and amount for {row.get('name') or 'Unnamed bill'}.",
    }


def summarize_bills_for_planning(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    rows = [validate_bill_record(row).to_dict() for row in _rows_from_snapshot(snapshot)]
    overdue = [r for r in rows if r.get("status") == "overdue"]
    upcoming = [r for r in rows if r.get("timing_status") == "upcoming"]
    high_risk = [r for r in rows if r.get("timing_status") == "at_risk"]
    clarifications = [
        build_bill_clarification(r)
        for r in rows
        if not r.get("due_date") or r.get("amount") is None
    ]
    warnings: list[str] = []
    if overdue:
        warnings.append(f"{len(overdue)} bill(s) overdue.")
    if high_risk:
        warnings.append(f"{len(high_risk)} bill(s) due soon or at risk.")
    return {
        "rows": rows,
        "overdue": overdue,
        "upcoming": upcoming,
        "high_risk": high_risk,
        "warnings": warnings,
        "clarifications": clarifications,
    }


def build_bills_snapshot() -> dict[str, Any]:
    bills = [b.to_dict() for b in load_manual_bills()]
    summary = summarize_bills_for_planning({"data": bills})
    payload = {
        "snapshot_type": "bills_snapshot",
        "generated_at": now_iso(),
        "stale": False,
        "confidence": 0.55 if bills else 0.25,
        "source_files_or_tools": [str(_manual_bills_path())],
        "missing_sources": [] if bills else ["manual_bills"],
        "errors": [],
        "data": bills,
        "summary_short": f"Bills: {len(bills)} record(s)",
        "summary_detailed": "Manual bills ingestion only; no payment actions.",
        "evidence_items": [],
        "suggested_questions": [c["message"] for c in summary.get("clarifications") or []],
    }
    from brain.live_work_orchestration.builders import live_work_dir

    out_dir = live_work_dir() / "ingestion"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "bills_snapshot.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
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
