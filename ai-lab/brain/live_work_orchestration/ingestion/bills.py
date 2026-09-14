from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
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
    source: str = "manual_bills"
    confidence: float = 0.5
    notes: str = ""
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _live_work_dir() -> Path:
    try:
        from brain.live_work_orchestration.builders import live_work_dir

        return live_work_dir()
    except Exception:
        d = _project_root() / "state" / "live_work_orchestration"
        d.mkdir(parents=True, exist_ok=True)
        return d


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except Exception:
        return None


def validate_bill_record(raw: dict[str, Any]) -> tuple[BillRecord | None, list[str]]:
    errors: list[str] = []
    name = str(raw.get("name") or raw.get("title") or raw.get("vendor") or "").strip()
    if not name:
        errors.append("missing_name")
    due_date = str(raw.get("due_date") or raw.get("due") or "").strip() or None
    if due_date and _parse_date(due_date) is None:
        errors.append("invalid_due_date")
    amount_raw = raw.get("amount")
    amount: float | None = None
    if amount_raw not in (None, ""):
        try:
            amount = float(amount_raw)
        except (TypeError, ValueError):
            errors.append("invalid_amount")
    if errors:
        return None, errors
    try:
        confidence = float(raw.get("confidence") or 0.75)
    except (TypeError, ValueError):
        confidence = 0.5
    evidence_raw = raw.get("evidence") or []
    if isinstance(evidence_raw, str):
        evidence = [evidence_raw]
    else:
        evidence = [str(x) for x in list(evidence_raw)]

    return (
        BillRecord(
            name=name,
            due_date=due_date,
            amount=amount,
            currency=str(raw.get("currency") or "USD"),
            status=str(raw.get("status") or "unknown").strip().lower() or "unknown",
            source=str(raw.get("source") or "manual_bills"),
            confidence=confidence,
            notes=str(raw.get("notes") or ""),
            evidence=evidence,
        ),
        [],
    )


def evaluate_bill_status(record: BillRecord | dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    row = record.to_dict() if isinstance(record, BillRecord) else dict(record)
    today = today or datetime.utcnow().date()
    due = _parse_date(row.get("due_date"))
    status = str(row.get("status") or "unknown").lower()
    if status in ("paid", "done", "cancelled"):
        timing = "settled"
        days_until_due = None
    elif due is None:
        timing = "unknown"
        days_until_due = None
    else:
        days_until_due = (due - today).days
        if days_until_due < 0:
            status = "overdue"
            timing = "at_risk"
        elif days_until_due <= 3:
            timing = "at_risk"
        elif days_until_due <= 14:
            timing = "upcoming"
        else:
            timing = "scheduled"
    row["status"] = status
    row["timing_status"] = timing
    row["days_until_due"] = days_until_due
    return row


def load_manual_bills() -> list[dict[str, Any]]:
    candidates = [
        _live_work_dir() / "manual_bills.json",
        _project_root() / "config" / "manual_bills.json",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows = raw.get("bills") if isinstance(raw, dict) else raw
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []


def build_bill_clarification(row: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    return {
        "message": f"Please confirm bill details for {row.get('name') or row.get('title') or 'unknown bill'}: {', '.join(errors)}.",
        "reason": "bill_details_missing_or_invalid",
        "source": "bills_ingestion",
        "target_list": "Agent Bills",
        "evidence": [str(row.get("source") or "manual_bills")],
    }


def summarize_bills_for_planning(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    warnings: list[str] = []
    if not isinstance(snapshot, dict):
        return {
            "upcoming": [],
            "overdue": [],
            "high_risk": [],
            "warnings": ["No bills snapshot available."],
            "clarifications": [],
        }
    data = snapshot.get("data")
    if isinstance(data, dict):
        rows = data.get("bills") or []
    else:
        rows = data or []
    bill_rows = [r for r in rows if isinstance(r, dict)]
    overdue = [r for r in bill_rows if r.get("status") == "overdue"]
    upcoming = [r for r in bill_rows if r.get("timing_status") in ("upcoming", "at_risk")]
    high_risk = [r for r in bill_rows if r.get("timing_status") == "at_risk"]
    clarifications = list(snapshot.get("suggested_questions") or [])
    for row in bill_rows:
        missing = [field for field in ("due_date", "amount") if row.get(field) in (None, "")]
        if missing:
            clarifications.append(build_bill_clarification(row, [f"missing_{x}" for x in missing]))
    if snapshot.get("missing_sources"):
        warnings.append(f"Missing bill sources: {snapshot.get('missing_sources')}")
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
    clarifications: list[dict[str, Any]] = []
    errors: list[str] = []
    for raw in raw_rows:
        record, row_errors = validate_bill_record(raw)
        if record is None:
            errors.extend(row_errors)
            clarifications.append(build_bill_clarification(raw, row_errors))
            continue
        rows.append(evaluate_bill_status(record))

    missing = [] if raw_rows else ["manual_bills"]
    snap = {
        "snapshot_type": "bills_snapshot",
        "generated_at": now_iso(),
        "stale": False,
        "confidence": 0.78 if rows else 0.35,
        "source_files_or_tools": ["manual_bills.json"],
        "missing_sources": missing,
        "errors": errors,
        "data": rows,
        "summary_short": f"Bills: {len(rows)} manual record(s)",
        "summary_detailed": "Manual-first financial obligations only; no payments, bank access, or forecasting.",
        "evidence_items": [
            {
                "title": "Bills ingestion",
                "summary": f"{len(rows)} valid manual bill record(s)",
                "source_path_or_tool": "manual_bills.json",
                "observed_at": now_iso(),
                "confidence": 0.75,
            }
        ],
        "suggested_questions": clarifications,
    }
    out_dir = _live_work_dir() / "ingestion"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "bills_snapshot.json").write_text(json.dumps(snap, indent=2, default=str), encoding="utf-8")
    return snap


__all__ = [
    "BillRecord",
    "build_bill_clarification",
    "build_bills_snapshot",
    "evaluate_bill_status",
    "load_manual_bills",
    "summarize_bills_for_planning",
    "validate_bill_record",
]
