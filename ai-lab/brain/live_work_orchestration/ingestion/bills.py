"""Manual-first bills ingestion for live work planning.

This lane is intentionally read-only with respect to external financial systems.
It only loads explicit local records and surfaces planning constraints.
"""
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
    due_date: str
    amount: float | None = None
    currency: str = "USD"
    status: str = "unknown"
    source: str = "manual_bills"
    notes: str = ""
    evidence: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["evidence"] = list(self.evidence or [])
        return out


def _parse_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _manual_bills_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    from brain.live_work_orchestration.builders import live_work_dir

    return live_work_dir() / "manual_bills.json"


def validate_bill_record(raw: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not str(raw.get("name") or "").strip():
        errors.append("name required")
    if not _parse_date(raw.get("due_date")):
        errors.append("due_date must be YYYY-MM-DD")
    amount = raw.get("amount")
    if amount not in (None, ""):
        try:
            float(amount)
        except (TypeError, ValueError):
            errors.append("amount must be numeric when present")
    return not errors, errors


def evaluate_bill_status(raw: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    due = _parse_date(raw.get("due_date"))
    status = str(raw.get("status") or "unknown").strip().lower() or "unknown"
    paid = status in {"paid", "done", "closed", "cancelled"}
    days_until_due = (due - today).days if due else None
    timing_status = "unknown"
    if paid:
        timing_status = "paid"
    elif days_until_due is not None:
        if days_until_due < 0:
            status = "overdue"
            timing_status = "overdue"
        elif days_until_due <= 7:
            timing_status = "at_risk"
        elif days_until_due <= 30:
            timing_status = "upcoming"
        else:
            timing_status = "future"

    try:
        amount = float(raw["amount"]) if raw.get("amount") not in (None, "") else None
    except (TypeError, ValueError):
        amount = None

    return {
        "name": str(raw.get("name") or "").strip(),
        "due_date": str(raw.get("due_date") or "").strip(),
        "amount": amount,
        "currency": str(raw.get("currency") or "USD").strip() or "USD",
        "status": status,
        "timing_status": timing_status,
        "days_until_due": days_until_due,
        "source": str(raw.get("source") or "manual_bills"),
        "notes": str(raw.get("notes") or ""),
        "evidence": list(raw.get("evidence") or []),
    }


def load_manual_bills(path: str | Path | None = None) -> list[dict[str, Any]]:
    p = _manual_bills_path(path)
    if not p.is_file():
        return []
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, dict):
        rows = payload.get("bills") or payload.get("items") or []
    else:
        rows = payload
    return [r for r in rows if isinstance(r, dict)]


def build_bill_clarification(row: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    return {
        "message": f"Clarify bill record {row.get('name') or '(unnamed)'}: {', '.join(errors)}",
        "reason": "bill_record_incomplete",
        "source": "bills_ingestion",
        "target_list": "Agent Bills",
        "evidence": list(row.get("evidence") or []),
    }


def summarize_bills_for_planning(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    rows = []
    if isinstance(snapshot, dict):
        data = snapshot.get("data")
        if isinstance(data, list):
            rows = [r for r in data if isinstance(r, dict)]
        elif isinstance(data, dict):
            rows = [r for r in data.get("bills", []) if isinstance(r, dict)]

    overdue = [r for r in rows if r.get("timing_status") == "overdue" or r.get("status") == "overdue"]
    upcoming = [r for r in rows if r.get("timing_status") in {"at_risk", "upcoming"}]
    high_risk = [r for r in rows if r.get("timing_status") in {"overdue", "at_risk"}]
    clarifications = []
    warnings = []
    if overdue:
        warnings.append(f"{len(overdue)} bill(s) are overdue.")
    if any(r.get("timing_status") == "at_risk" for r in rows):
        warnings.append("Bills due within 7 days may constrain planning.")
    for r in rows:
        missing = []
        if not r.get("name"):
            missing.append("name")
        if not r.get("due_date"):
            missing.append("due_date")
        if missing:
            clarifications.append(build_bill_clarification(r, missing))
    return {
        "upcoming": upcoming,
        "overdue": overdue,
        "high_risk": high_risk,
        "warnings": warnings,
        "clarifications": clarifications,
    }


def build_bills_snapshot() -> dict[str, Any]:
    raw_rows = load_manual_bills()
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    clarifications: list[dict[str, Any]] = []
    for raw in raw_rows:
        ok, errs = validate_bill_record(raw)
        if not ok:
            errors.extend(errs)
            clarifications.append(build_bill_clarification(raw, errs))
        rows.append(evaluate_bill_status(raw))

    summary = summarize_bills_for_planning({"data": rows})
    snapshot = {
        "snapshot_type": "bills_snapshot",
        "generated_at": now_iso(),
        "freshness_seconds": 3600,
        "source_files_or_tools": [str(_manual_bills_path())],
        "confidence": 0.75 if raw_rows else 0.45,
        "stale": False,
        "errors": errors,
        "data": rows,
        "summary_short": f"Bills: {len(rows)} manual record(s); {len(summary['overdue'])} overdue",
        "summary_detailed": "Manual bills only; no bank/payment mutations or external financial reads.",
        "suggested_questions": [],
        "evidence_items": [],
        "clarifications": clarifications,
    }

    from brain.live_work_orchestration.builders import live_work_dir

    out = live_work_dir() / "ingestion" / "bills_snapshot.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return snapshot


__all__ = [
    "BillRecord",
    "build_bill_clarification",
    "build_bills_snapshot",
    "evaluate_bill_status",
    "load_manual_bills",
    "summarize_bills_for_planning",
    "validate_bill_record",
]
