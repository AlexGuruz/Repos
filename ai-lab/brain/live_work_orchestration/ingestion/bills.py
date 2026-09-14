from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from brain.prepared_context.schema import now_iso


@dataclass(frozen=True)
class BillRecord:
    id: str
    name: str
    company: str | None = None
    amount_due: float | None = None
    due_date: str | None = None
    status: str = "unknown"
    priority: str = "normal"
    source: str = "manual"
    notes: str | None = None


def _live_work_dir() -> Path:
    try:
        from brain.live_work_orchestration.builders import live_work_dir

        return live_work_dir()
    except Exception:
        root = Path(__file__).resolve().parents[3]
        d = root / "state" / "live_work_orchestration"
        d.mkdir(parents=True, exist_ok=True)
        return d


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _coerce_bill(raw: dict[str, Any], index: int) -> BillRecord:
    return BillRecord(
        id=str(raw.get("id") or raw.get("bill_id") or f"bill-{index}"),
        name=str(raw.get("name") or raw.get("title") or raw.get("vendor") or "Unknown bill"),
        company=str(raw.get("company")).strip() if raw.get("company") else None,
        amount_due=float(raw["amount_due"]) if raw.get("amount_due") not in (None, "") else None,
        due_date=str(raw.get("due_date")).strip() if raw.get("due_date") else None,
        status=str(raw.get("status") or "unknown").strip().lower(),
        priority=str(raw.get("priority") or "normal").strip().lower(),
        source=str(raw.get("source") or "manual").strip() or "manual",
        notes=str(raw.get("notes")).strip() if raw.get("notes") else None,
    )


def validate_bill_record(record: BillRecord | dict[str, Any]) -> list[str]:
    row = asdict(record) if isinstance(record, BillRecord) else dict(record)
    errors: list[str] = []
    if not str(row.get("name") or "").strip():
        errors.append("missing_name")
    if row.get("amount_due") is None:
        errors.append("missing_amount_due")
    if _parse_date(row.get("due_date")) is None:
        errors.append("missing_or_invalid_due_date")
    return errors


def evaluate_bill_status(record: BillRecord | dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    row = asdict(record) if isinstance(record, BillRecord) else dict(record)
    today = today or date.today()
    due = _parse_date(row.get("due_date"))
    base_status = str(row.get("status") or "unknown").lower()
    paid = base_status in {"paid", "complete", "completed"}
    days_until = (due - today).days if due else None
    timing = "unknown"
    status = base_status
    if paid:
        timing = "paid"
        status = "paid"
    elif days_until is None:
        timing = "unknown"
        status = "unknown"
    elif days_until < 0:
        timing = "overdue"
        status = "overdue"
    elif days_until <= 3:
        timing = "at_risk"
        status = "due_soon"
    elif days_until <= 14:
        timing = "upcoming"
        status = "upcoming"
    else:
        timing = "scheduled"
        status = "scheduled"

    out = dict(row)
    out.update(
        {
            "status": status,
            "timing_status": timing,
            "days_until_due": days_until,
            "validation_errors": validate_bill_record(row),
            "planning_constraint": timing in {"overdue", "at_risk", "upcoming"},
            "high_risk": timing == "overdue" or str(row.get("priority") or "").lower() == "high",
        }
    )
    return out


def _candidate_files() -> list[Path]:
    env = os.environ.get("AI_LAB_BILLS_PATH")
    candidates = [Path(env)] if env else []
    live = _live_work_dir()
    root = Path(__file__).resolve().parents[3]
    candidates.extend(
        [
            live / "manual_bills.json",
            root / "config" / "manual_bills.json",
            root / "config" / "bills.json",
        ]
    )
    return candidates


def load_manual_bills(path: str | Path | None = None) -> list[BillRecord]:
    files = [Path(path)] if path else _candidate_files()
    for p in files:
        if not p.is_file():
            continue
        payload = json.loads(p.read_text(encoding="utf-8"))
        rows = payload.get("bills") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        return [_coerce_bill(row, i) for i, row in enumerate(rows) if isinstance(row, dict)]
    return []


def build_bill_clarification(record: BillRecord | dict[str, Any]) -> dict[str, Any] | None:
    row = asdict(record) if isinstance(record, BillRecord) else dict(record)
    errors = validate_bill_record(row)
    if not errors:
        return None
    return {
        "message": f"Confirm bill details for {row.get('name') or 'Unknown bill'}: {', '.join(errors)}.",
        "reason": "bill_details_missing",
        "source": "bills_ingestion",
        "target_list": "Agent Bills",
        "evidence": [str(row.get("id") or "")],
    }


def summarize_bills_for_planning(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    data = (snapshot or {}).get("data") if isinstance(snapshot, dict) else None
    if isinstance(data, dict):
        rows = list(data.get("bills") or [])
    elif isinstance(data, list):
        rows = data
    else:
        rows = []
    evaluated = [evaluate_bill_status(r) for r in rows if isinstance(r, dict)]
    return {
        "upcoming": [r for r in evaluated if r.get("timing_status") == "upcoming"],
        "overdue": [r for r in evaluated if r.get("timing_status") == "overdue"],
        "high_risk": [r for r in evaluated if r.get("high_risk")],
        "warnings": [r for r in evaluated if r.get("validation_errors")],
        "clarifications": [c for r in evaluated if (c := build_bill_clarification(r))],
    }


def build_bills_snapshot() -> dict[str, Any]:
    records = load_manual_bills()
    rows = [evaluate_bill_status(r) for r in records]
    summary = summarize_bills_for_planning({"data": rows})
    missing = [] if records else ["manual_bills"]
    payload = {
        "snapshot_type": "bills_snapshot",
        "generated_at": now_iso(),
        "freshness_seconds": 300,
        "stale": False,
        "confidence": 0.85 if records else 0.45,
        "source_files_or_tools": ["manual_bills_json"],
        "missing_sources": missing,
        "errors": [],
        "data": rows,
        "summary_short": f"Bills snapshot: {len(rows)} manual bill(s), {len(summary['overdue'])} overdue",
        "summary_detailed": "Manual bills lane only; no payments, bank mutations, or external bank APIs.",
        "evidence_items": [],
        "suggested_questions": [],
    }
    out = _live_work_dir() / "ingestion" / "bills_snapshot.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return payload
