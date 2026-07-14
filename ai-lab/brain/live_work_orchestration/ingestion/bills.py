from __future__ import annotations

import csv
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
    status: str = "open"
    source: str = "manual"
    target_list: str = "Agent Bills"
    notes: str = ""


def _live_work_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "state" / "live_work_orchestration"


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None


def _today() -> date:
    return datetime.now(timezone.utc).date()


def validate_bill_record(row: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    if not str(row.get("name") or "").strip():
        issues.append("missing_name")
    if _parse_date(row.get("due_date")) is None:
        issues.append("missing_or_invalid_due_date")
    amount = row.get("amount")
    if amount not in (None, ""):
        try:
            if float(amount) < 0:
                issues.append("negative_amount")
        except (TypeError, ValueError):
            issues.append("invalid_amount")
    return issues


def evaluate_bill_status(row: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    out = dict(row)
    due = _parse_date(out.get("due_date"))
    ref = today or _today()
    if due is None:
        out["status"] = out.get("status") or "needs_clarification"
        out["timing_status"] = "unknown"
        out["days_until_due"] = None
        return out
    days = (due - ref).days
    status = str(out.get("status") or "open").lower()
    if status not in ("paid", "closed"):
        if days < 0:
            status = "overdue"
        elif days <= 3:
            status = "due_soon"
        else:
            status = "open"
    out["status"] = status
    out["days_until_due"] = days
    if days < 0:
        out["timing_status"] = "at_risk"
    elif days <= 7:
        out["timing_status"] = "upcoming"
    else:
        out["timing_status"] = "future"
    return out


def build_bill_clarification(row: dict[str, Any], issues: list[str] | None = None) -> dict[str, Any]:
    problems = issues or validate_bill_record(row)
    return {
        "target_list": str(row.get("target_list") or "Agent Bills"),
        "message": f"Clarify bill record {row.get('name') or '(unnamed)'}: {', '.join(problems)}",
        "reason": "bill_record_incomplete",
        "source": row.get("source") or "manual",
        "evidence": [str(row.get("name") or ""), str(row.get("due_date") or "")],
    }


def _coerce_bill(row: dict[str, Any]) -> dict[str, Any]:
    amount_raw = row.get("amount")
    amount: float | None
    try:
        amount = float(amount_raw) if amount_raw not in (None, "") else None
    except (TypeError, ValueError):
        amount = None
    bill = BillRecord(
        name=str(row.get("name") or row.get("vendor") or "").strip(),
        due_date=str(row.get("due_date") or "").strip(),
        amount=amount,
        currency=str(row.get("currency") or "USD").strip() or "USD",
        status=str(row.get("status") or "open").strip() or "open",
        source=str(row.get("source") or "manual").strip() or "manual",
        target_list=str(row.get("target_list") or "Agent Bills").strip() or "Agent Bills",
        notes=str(row.get("notes") or "").strip(),
    )
    return asdict(bill)


def load_manual_bills(path: str | Path | None = None) -> list[dict[str, Any]]:
    if path is None:
        path = _live_work_dir() / "manual_bills.json"
    p = Path(path)
    if not p.is_file():
        return []
    try:
        if p.suffix.lower() == ".csv":
            with p.open("r", encoding="utf-8", newline="") as handle:
                return [_coerce_bill(row) for row in csv.DictReader(handle)]
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = data.get("bills") if isinstance(data, dict) else data
    return [_coerce_bill(row) for row in rows or [] if isinstance(row, dict)]


def summarize_bills_for_planning(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    rows = [r for r in ((snapshot or {}).get("data") or []) if isinstance(r, dict)]
    warnings: list[str] = []
    clarifications: list[dict[str, Any]] = []
    overdue = [r for r in rows if r.get("status") == "overdue"]
    due_soon = [r for r in rows if r.get("timing_status") in ("at_risk", "upcoming")]
    if overdue:
        warnings.append(f"{len(overdue)} overdue bill(s) require manual attention.")
    elif due_soon:
        warnings.append(f"{len(due_soon)} bill(s) are due soon; keep plan capacity flexible.")
    for row in rows:
        issues = validate_bill_record(row)
        if issues:
            clarifications.append(build_bill_clarification(row, issues))
    return {
        "total": len(rows),
        "overdue_count": len(overdue),
        "due_soon_count": len(due_soon),
        "warnings": warnings,
        "clarifications": clarifications,
    }


def build_bills_snapshot(path: str | Path | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for row in load_manual_bills(path):
        issues = validate_bill_record(row)
        if issues:
            errors.append(f"{row.get('name') or '(unnamed)'}:{','.join(issues)}")
        rows.append(evaluate_bill_status(row))
    summary = summarize_bills_for_planning({"data": rows})
    snap = {
        "snapshot_type": "bills_snapshot",
        "generated_at": now_iso(),
        "freshness_seconds": 24 * 60 * 60,
        "stale": False,
        "confidence": 0.75 if rows else 0.35,
        "source_files_or_tools": [str(path or (_live_work_dir() / "manual_bills.json"))],
        "missing_sources": [] if rows else ["manual_bills"],
        "errors": errors,
        "data": rows,
        "summary_short": f"Bills: {len(rows)} manual record(s)",
        "summary_detailed": "Manual-first bills snapshot; no payments, bank access, or external writes.",
        "evidence_items": [],
        "suggested_questions": [],
        "planning_summary": summary,
    }
    out_dir = _live_work_dir() / "ingestion"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "bills_snapshot.json").write_text(json.dumps(snap, indent=2), encoding="utf-8")
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
