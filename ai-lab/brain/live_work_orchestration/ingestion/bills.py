"""Read-only bills / financial-obligations ingestion lane."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from brain.prepared_context.schema import now_iso


@dataclass
class BillRecord:
    name: str
    due_date: str
    amount: float | None = None
    currency: str = "USD"
    status: str = "open"
    source: str = "manual"
    company: str = ""
    notes: str = ""
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _live_work_dir() -> Path:
    from brain.live_work_orchestration.builders import live_work_dir

    return live_work_dir()


def _parse_due_date(value: str) -> date | None:
    text = (value or "").strip()
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


def validate_bill_record(record: dict[str, Any] | BillRecord) -> list[str]:
    row = record.to_dict() if isinstance(record, BillRecord) else dict(record or {})
    errors: list[str] = []
    if not str(row.get("name") or "").strip():
        errors.append("missing_name")
    if not _parse_due_date(str(row.get("due_date") or "")):
        errors.append("missing_or_invalid_due_date")
    amount = row.get("amount")
    if amount not in (None, ""):
        try:
            if float(amount) < 0:
                errors.append("negative_amount")
        except (TypeError, ValueError):
            errors.append("invalid_amount")
    return errors


def evaluate_bill_status(record: dict[str, Any] | BillRecord, *, today: date | None = None) -> dict[str, Any]:
    row = record.to_dict() if isinstance(record, BillRecord) else dict(record or {})
    due = _parse_due_date(str(row.get("due_date") or ""))
    current = today or datetime.now(timezone.utc).date()
    status = str(row.get("status") or "open").strip().lower() or "open"
    days_until_due = (due - current).days if due else None
    timing_status = "unknown"
    if status in {"paid", "done", "closed"}:
        timing_status = "settled"
    elif days_until_due is None:
        timing_status = "unknown"
    elif days_until_due < 0:
        status = "overdue"
        timing_status = "at_risk"
    elif days_until_due <= 7:
        timing_status = "at_risk"
    elif days_until_due <= 30:
        timing_status = "upcoming"
    else:
        timing_status = "scheduled"
    row.update(
        {
            "due_date": due.isoformat() if due else str(row.get("due_date") or ""),
            "status": status,
            "days_until_due": days_until_due,
            "timing_status": timing_status,
            "validation_errors": validate_bill_record(row),
        }
    )
    return row


def build_bill_clarification(record: dict[str, Any]) -> dict[str, Any] | None:
    errors = list(record.get("validation_errors") or validate_bill_record(record))
    if not errors:
        return None
    from brain.live_work_orchestration.clickup_routing import route_comment

    name = str(record.get("name") or "Unnamed bill")
    company = str(record.get("company") or "").strip()
    route = route_comment({"message": f"{company} bill clarification {name}"})
    return {
        "message": f"Clarify bill fields for {name}: {', '.join(errors)}",
        "reason": "bill_record_incomplete",
        "source": "bills_ingestion",
        "evidence": list(record.get("evidence") or []),
        **route,
    }


def load_manual_bills(path: Path | None = None) -> list[BillRecord]:
    root = _live_work_dir()
    candidates = [
        path,
        root / "manual_bills.json",
        root / "ingestion" / "manual_bills.json",
    ]
    source = next((p for p in candidates if p is not None and p.is_file()), None)
    if source is None:
        return []
    raw = json.loads(source.read_text(encoding="utf-8"))
    rows = raw.get("bills") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return []
    out: list[BillRecord] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        amount = None
        if item.get("amount") not in (None, ""):
            try:
                amount = float(item["amount"])
            except (TypeError, ValueError):
                amount = None
        out.append(
            BillRecord(
                name=str(item.get("name") or item.get("vendor") or "").strip(),
                due_date=str(item.get("due_date") or "").strip(),
                amount=amount,
                currency=str(item.get("currency") or "USD"),
                status=str(item.get("status") or "open"),
                source=str(item.get("source") or f"manual:{source.name}"),
                company=str(item.get("company") or ""),
                notes=str(item.get("notes") or ""),
                evidence=[str(x) for x in list(item.get("evidence") or [])],
            )
        )
    return out


def summarize_bills_for_planning(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    data = snapshot.get("data") if isinstance(snapshot, dict) else {}
    rows = data if isinstance(data, list) else (data.get("bills") if isinstance(data, dict) else [])
    bills = [r for r in list(rows or []) if isinstance(r, dict)]
    overdue = [r for r in bills if r.get("status") == "overdue"]
    upcoming = [r for r in bills if r.get("timing_status") == "upcoming"]
    high_risk = [r for r in bills if r.get("timing_status") == "at_risk"]
    clarifications = []
    for row in bills:
        proposal = build_bill_clarification(row)
        if proposal:
            clarifications.append(proposal)
    warnings = [f"{len(overdue)} overdue bill(s)"] if overdue else []
    warnings.extend(f"{r.get('name')} due in {r.get('days_until_due')} day(s)" for r in high_risk[:5])
    return {
        "overdue": overdue,
        "upcoming": upcoming,
        "high_risk": high_risk,
        "warnings": warnings,
        "clarifications": clarifications,
    }


def build_bills_snapshot() -> dict[str, Any]:
    bills = [evaluate_bill_status(bill) for bill in load_manual_bills()]
    clarifications = [p for p in (build_bill_clarification(row) for row in bills) if p]
    errors = [f"{row.get('name') or 'unnamed'}:{','.join(row.get('validation_errors') or [])}" for row in bills if row.get("validation_errors")]
    payload = {
        "snapshot_type": "bills_snapshot",
        "generated_at": now_iso(),
        "stale": False,
        "confidence": 0.75 if bills else 0.35,
        "source_files_or_tools": ["state/live_work_orchestration/manual_bills.json"],
        "missing_sources": [] if bills else ["manual_bills_json"],
        "errors": errors,
        "data": {"bills": bills, "clarifications": clarifications},
        "summary_short": f"Bills snapshot: {len(bills)} manual record(s)",
        "summary_detailed": "Manual bills only; no payments, bank mutations, forecasts, or external financial API calls.",
        "evidence_items": [
            {
                "title": "Bills ingestion",
                "summary": f"{len(bills)} manual financial obligation record(s)",
                "source_path_or_tool": "state/live_work_orchestration/manual_bills.json",
                "observed_at": now_iso(),
                "confidence": 0.75 if bills else 0.35,
            }
        ],
        "suggested_questions": [p["message"] for p in clarifications],
    }
    ingestion_dir = _live_work_dir() / "ingestion"
    ingestion_dir.mkdir(parents=True, exist_ok=True)
    (ingestion_dir / "bills_snapshot.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
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
