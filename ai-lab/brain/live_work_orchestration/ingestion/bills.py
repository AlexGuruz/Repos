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
    due_date: str = ""
    amount: float | None = None
    currency: str = "USD"
    status: str = "unknown"
    timing_status: str = "unknown"
    days_until_due: int | None = None
    source: str = "manual"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _live_work_ingestion_dir() -> Path:
    from brain.live_work_orchestration.builders import live_work_dir

    d = live_work_dir() / "ingestion"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _manual_bills_path() -> Path:
    return Path(__file__).resolve().parents[3] / "state" / "live_work_orchestration" / "manual_bills.json"


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        pass
    try:
        return date.fromisoformat(text)
    except Exception:
        return None


def evaluate_bill_status(row: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    due = _parse_date(row.get("due_date"))
    out = dict(row)
    if due is None:
        out.setdefault("status", "unknown")
        out.setdefault("timing_status", "unknown")
        out["days_until_due"] = None
        return out
    days = (due - today).days
    out["days_until_due"] = days
    if days < 0:
        out["status"] = "overdue"
        out["timing_status"] = "overdue"
    elif days <= 3:
        out["status"] = str(out.get("status") or "open")
        out["timing_status"] = "at_risk"
    elif days <= 14:
        out["status"] = str(out.get("status") or "open")
        out["timing_status"] = "upcoming"
    else:
        out["status"] = str(out.get("status") or "open")
        out["timing_status"] = "scheduled"
    return out


def validate_bill_record(row: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not str(row.get("name") or "").strip():
        errors.append("name_required")
    if row.get("due_date") and _parse_date(row.get("due_date")) is None:
        errors.append("invalid_due_date")
    return not errors, errors


def build_bill_clarification(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_list": "Agent Clarifications",
        "message": f"Clarify bill details for {row.get('name') or 'unknown bill'}.",
        "reason": "bill_record_incomplete",
        "approval_required": True,
        "evidence": [str(row.get("source") or "manual")],
    }


def load_manual_bills(path: Path | None = None) -> list[dict[str, Any]]:
    p = path or _manual_bills_path()
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = raw.get("bills") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return []
    return [dict(r) for r in rows if isinstance(r, dict)]


def summarize_bills_for_planning(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    rows = []
    if isinstance(snapshot, dict):
        data = snapshot.get("data")
        if isinstance(data, list):
            rows = [r for r in data if isinstance(r, dict)]
    upcoming = [r for r in rows if r.get("timing_status") == "upcoming"]
    overdue = [r for r in rows if r.get("status") == "overdue"]
    high_risk = [r for r in rows if r.get("timing_status") in ("overdue", "at_risk")]
    warnings = []
    if overdue:
        warnings.append(f"{len(overdue)} overdue bill(s) need review.")
    if high_risk:
        warnings.append(f"{len(high_risk)} bill(s) are overdue or at risk.")
    clarifications = [
        build_bill_clarification(r)
        for r in rows
        if not validate_bill_record(r)[0] or r.get("timing_status") == "unknown"
    ]
    return {
        "upcoming": upcoming,
        "overdue": overdue,
        "high_risk": high_risk,
        "warnings": warnings,
        "clarifications": clarifications,
    }


def build_bills_snapshot() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for raw in load_manual_bills():
        row = evaluate_bill_status(raw)
        ok, row_errors = validate_bill_record(row)
        if not ok:
            errors.extend([f"{row.get('name') or 'unknown'}:{e}" for e in row_errors])
        if not str(row.get("name") or "").strip():
            row["name"] = "unknown bill"
        record_kwargs = {k: row[k] for k in BillRecord.__dataclass_fields__ if k in row and row[k] is not None}
        rows.append(BillRecord(**record_kwargs).to_dict())
    summary = summarize_bills_for_planning({"data": rows})
    payload = {
        "snapshot_type": "bills_snapshot",
        "generated_at": now_iso(),
        "stale": False,
        "confidence": 0.7 if rows else 0.35,
        "source_files_or_tools": [str(_manual_bills_path())],
        "missing_sources": [] if rows else ["manual_bills"],
        "errors": errors,
        "data": rows,
        "summary_short": f"Bills snapshot: {len(rows)} manual row(s)",
        "summary_detailed": "Read-only manual bills snapshot; no payment actions.",
        "evidence_items": [],
        "suggested_questions": [],
        "planning_summary": summary,
    }
    out = _live_work_ingestion_dir() / "bills_snapshot.json"
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
