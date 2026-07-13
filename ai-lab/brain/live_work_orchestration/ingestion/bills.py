from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from brain.prepared_context.schema import now_iso


@dataclass(frozen=True)
class BillRecord:
    name: str
    due_date: str
    amount: float | None = None
    currency: str = "USD"
    status: str = "open"
    category: str = "agent_bills"
    source: str = "manual"
    notes: str = ""


def _bills_path() -> Path:
    override = os.environ.get("AI_LAB_BILLS_FILE")
    if override:
        return Path(override)
    root = Path(__file__).resolve().parents[3]
    return root / "state" / "live_work_orchestration" / "manual_bills.json"


def _ingestion_dir() -> Path:
    root = Path(__file__).resolve().parents[3]
    d = root / "state" / "live_work_orchestration" / "ingestion"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _parse_date(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def validate_bill_record(raw: dict[str, Any]) -> tuple[BillRecord | None, list[str]]:
    missing: list[str] = []
    name = str(raw.get("name") or raw.get("vendor") or "").strip()
    due_date = str(raw.get("due_date") or "").strip()
    if not name:
        missing.append("name")
    if not due_date or _parse_date(due_date) is None:
        missing.append("due_date")
    if missing:
        return None, missing
    amount_raw = raw.get("amount")
    amount: float | None
    try:
        amount = float(amount_raw) if amount_raw not in (None, "") else None
    except (TypeError, ValueError):
        amount = None
        missing.append("amount")
    return (
        BillRecord(
            name=name,
            due_date=due_date[:10],
            amount=amount,
            currency=str(raw.get("currency") or "USD").strip() or "USD",
            status=str(raw.get("status") or "open").strip().lower() or "open",
            category=str(raw.get("category") or "agent_bills").strip() or "agent_bills",
            source=str(raw.get("source") or "manual").strip() or "manual",
            notes=str(raw.get("notes") or "").strip(),
        ),
        missing,
    )


def evaluate_bill_status(record: BillRecord, *, today: date | None = None) -> dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    due = _parse_date(record.due_date)
    paid = record.status in ("paid", "done", "closed")
    days_until_due = (due - today).days if due else None
    if paid:
        status = "paid"
        timing = "paid"
    elif days_until_due is None:
        status = "unknown"
        timing = "needs_clarification"
    elif days_until_due < 0:
        status = "overdue"
        timing = "at_risk"
    elif days_until_due <= 3:
        status = "open"
        timing = "at_risk"
    elif days_until_due <= 14:
        status = "open"
        timing = "upcoming"
    else:
        status = "open"
        timing = "later"
    return {
        **asdict(record),
        "status": status,
        "timing_status": timing,
        "days_until_due": days_until_due,
    }


def build_bill_clarification(raw: dict[str, Any], missing: list[str]) -> dict[str, Any]:
    category = str(raw.get("category") or "agent_bills").strip() or "agent_bills"
    target = {
        "company_finances": "Company Finances",
        "nugz_bills": "Nugz Bills",
    }.get(category, "Agent Bills")
    label = str(raw.get("name") or raw.get("vendor") or "bill").strip()
    return {
        "source": "bills_ingestion",
        "target_list": target,
        "reason": "missing_bill_fields",
        "message": f"Please confirm {', '.join(missing)} for {label}.",
        "evidence": [str(raw.get("source") or "manual_bills")],
        "status": "proposed",
    }


def load_manual_bills(path: Path | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    p = path or _bills_path()
    if not p.is_file():
        return [], [str(p)]
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return [], [str(p)]
    rows = data.get("bills") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return [], [str(p)]
    return [r for r in rows if isinstance(r, dict)], []


def summarize_bills_for_planning(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    rows = []
    if isinstance(snapshot, dict):
        data = snapshot.get("data") if isinstance(snapshot.get("data"), dict) else {}
        rows = [r for r in list(data.get("bills") or data.get("rows") or []) if isinstance(r, dict)]
    overdue = [r for r in rows if r.get("status") == "overdue"]
    upcoming = [r for r in rows if r.get("timing_status") == "upcoming"]
    high_risk = [r for r in rows if r.get("timing_status") == "at_risk"]
    warnings = []
    if overdue:
        warnings.append(f"{len(overdue)} bill(s) overdue")
    if high_risk:
        warnings.append(f"{len(high_risk)} bill(s) due within 3 days or overdue")
    return {
        "overdue": overdue,
        "upcoming": upcoming,
        "high_risk": high_risk,
        "warnings": warnings,
        "clarifications": list((snapshot or {}).get("suggested_questions") or []),
    }


def build_bills_snapshot() -> dict[str, Any]:
    raw_rows, missing_sources = load_manual_bills()
    rows: list[dict[str, Any]] = []
    clarifications: list[dict[str, Any]] = []
    errors: list[str] = []
    for raw in raw_rows:
        record, missing = validate_bill_record(raw)
        if missing:
            clarifications.append(build_bill_clarification(raw, missing))
        if record is None:
            errors.append(f"invalid bill row missing {','.join(missing)}")
            continue
        rows.append(evaluate_bill_status(record))

    summary = summarize_bills_for_planning({"data": {"bills": rows}, "suggested_questions": clarifications})
    payload = {
        "snapshot_type": "bills_snapshot",
        "generated_at": now_iso(),
        "stale": False,
        "confidence": 0.85 if raw_rows else 0.55,
        "source_files_or_tools": [str(_bills_path())],
        "missing_sources": missing_sources,
        "errors": errors,
        "data": {
            "bills": rows,
            "overdue_count": len(summary["overdue"]),
            "upcoming_count": len(summary["upcoming"]),
            "high_risk_count": len(summary["high_risk"]),
        },
        "summary_short": f"Bills: {len(rows)} valid manual rows; {len(summary['overdue'])} overdue",
        "summary_detailed": "Manual bills ingestion only; no payment, bank, or external finance mutations.",
        "evidence_items": [
            {
                "title": "Manual bills",
                "summary": f"{len(raw_rows)} row(s) loaded from local JSON",
                "source_path_or_tool": str(_bills_path()),
                "observed_at": now_iso(),
                "confidence": 0.8,
            }
        ],
        "suggested_questions": clarifications,
    }
    (_ingestion_dir() / "bills_snapshot.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
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
