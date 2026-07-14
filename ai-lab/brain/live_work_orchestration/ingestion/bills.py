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
    status: str = "unknown"
    source: str = "manual_bills"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _parse_date(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def validate_bill_record(row: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not str(row.get("name") or "").strip():
        errors.append("missing name")
    if row.get("due_date") and _parse_date(row.get("due_date")) is None:
        errors.append("invalid due_date")
    amount = row.get("amount")
    if amount not in (None, ""):
        try:
            float(amount)
        except (TypeError, ValueError):
            errors.append("invalid amount")
    return not errors, errors


def evaluate_bill_status(row: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    today = today or _today()
    out = dict(row)
    due = _parse_date(out.get("due_date"))
    paid = str(out.get("status") or "").lower() == "paid" or bool(out.get("paid"))
    if due is None:
        out["status"] = "unknown" if not paid else "paid"
        out["timing_status"] = "missing_due_date"
        out["days_until_due"] = None
        return out

    days = (due - today).days
    out["days_until_due"] = days
    if paid:
        out["status"] = "paid"
        out["timing_status"] = "paid"
    elif days < 0:
        out["status"] = "overdue"
        out["timing_status"] = "overdue"
    elif days <= 3:
        out["status"] = "open"
        out["timing_status"] = "at_risk"
    elif days <= 14:
        out["status"] = "open"
        out["timing_status"] = "upcoming"
    else:
        out["status"] = "open"
        out["timing_status"] = "scheduled"
    return out


def _manual_bills_path() -> Path:
    from brain.live_work_orchestration.builders import live_work_dir

    return live_work_dir() / "manual_bills.json"


def load_manual_bills(path: str | Path | None = None) -> list[dict[str, Any]]:
    p = Path(path) if path is not None else _manual_bills_path()
    if not p.is_file():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(raw, dict):
        rows = raw.get("bills") or raw.get("items") or []
    else:
        rows = raw
    if not isinstance(rows, list):
        return []
    return [dict(r) for r in rows if isinstance(r, dict)]


def build_bill_clarification(row: dict[str, Any], errors: list[str] | None = None) -> dict[str, Any]:
    return {
        "message": f"Clarify bill record for {row.get('name') or 'unnamed bill'}",
        "reason": ", ".join(errors or ["missing_bill_detail"]),
        "target_list": "Agent Bills",
        "evidence": [str(row.get("source") or "manual_bills")],
    }


def _rows_from_snapshot(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(snapshot, dict):
        return []
    data = snapshot.get("data")
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        rows = data.get("bills") or data.get("items") or []
        return [r for r in rows if isinstance(r, dict)]
    return []


def summarize_bills_for_planning(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    rows = _rows_from_snapshot(snapshot)
    upcoming = [r for r in rows if r.get("timing_status") == "upcoming"]
    overdue = [r for r in rows if r.get("status") == "overdue"]
    high_risk = [r for r in rows if r.get("timing_status") in ("at_risk", "overdue")]
    clarifications = [
        build_bill_clarification(r, ["missing due date"])
        for r in rows
        if r.get("timing_status") == "missing_due_date"
    ]
    warnings: list[str] = []
    if overdue:
        warnings.append(f"{len(overdue)} bill(s) overdue")
    at_risk = [r for r in rows if r.get("timing_status") == "at_risk"]
    if at_risk:
        warnings.append(f"{len(at_risk)} bill(s) due within 3 days")
    if clarifications:
        warnings.append(f"{len(clarifications)} bill record(s) need clarification")
    return {
        "upcoming": upcoming,
        "overdue": overdue,
        "high_risk": high_risk,
        "warnings": warnings,
        "clarifications": clarifications,
    }


def build_bills_snapshot() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    clarifications: list[dict[str, Any]] = []
    for raw in load_manual_bills():
        ok, errs = validate_bill_record(raw)
        if not ok:
            warnings.append(f"{raw.get('name') or 'unnamed bill'}: {', '.join(errs)}")
            clarifications.append(build_bill_clarification(raw, errs))
        row = evaluate_bill_status(raw)
        rows.append(row)

    summary = summarize_bills_for_planning({"data": rows})
    payload = {
        "snapshot_type": "bills_snapshot",
        "generated_at": now_iso(),
        "freshness_seconds": 3600,
        "source_files_or_tools": [str(_manual_bills_path())],
        "confidence": 0.85 if rows else 0.45,
        "stale": False,
        "errors": [],
        "missing_sources": [] if rows else ["manual_bills"],
        "data": rows,
        "summary_short": f"Bills: {len(rows)} record(s), {len(summary['overdue'])} overdue",
        "summary_detailed": "Read-only bill snapshot from local manual_bills.json; no payment or external actions.",
        "suggested_questions": [],
        "evidence_items": [
            {"label": "Manual bills", "value": f"{len(rows)} local record(s)", "source": str(_manual_bills_path())}
        ],
        "warnings": warnings + list(summary.get("warnings") or []),
        "clarifications": clarifications + list(summary.get("clarifications") or []),
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
