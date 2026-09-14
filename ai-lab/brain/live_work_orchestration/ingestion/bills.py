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
    due_date: str
    amount: float | None = None
    currency: str = "USD"
    status: str = "unknown"
    source: str = "manual"
    notes: str = ""


def _parse_date(value: str | None) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        try:
            return date.fromisoformat(text[:10])
        except Exception:
            return None


def evaluate_bill_status(record: BillRecord, *, today: date | None = None) -> dict[str, Any]:
    cur = today or datetime.now(timezone.utc).date()
    due = _parse_date(record.due_date)
    status = (record.status or "unknown").strip().lower()
    days_until_due: int | None = None
    timing_status = "unknown"
    if due is not None:
        days_until_due = (due - cur).days
        if status in ("paid", "done", "closed"):
            timing_status = "paid"
        elif days_until_due < 0:
            status = "overdue"
            timing_status = "at_risk"
        elif days_until_due <= 7:
            timing_status = "at_risk"
        elif days_until_due <= 30:
            timing_status = "upcoming"
        else:
            timing_status = "scheduled"
    return {
        "status": status,
        "timing_status": timing_status,
        "days_until_due": days_until_due,
    }


def validate_bill_record(raw: dict[str, Any]) -> tuple[BillRecord | None, list[str]]:
    errors: list[str] = []
    name = str(raw.get("name") or raw.get("title") or "").strip()
    due_date = str(raw.get("due_date") or raw.get("due") or "").strip()
    if not name:
        errors.append("name_required")
    if not due_date:
        errors.append("due_date_required")
    amount: float | None = None
    if raw.get("amount") not in (None, ""):
        try:
            amount = float(raw.get("amount"))
        except (TypeError, ValueError):
            errors.append("amount_invalid")
    if errors:
        return None, errors
    return (
        BillRecord(
            name=name,
            due_date=due_date,
            amount=amount,
            currency=str(raw.get("currency") or "USD"),
            status=str(raw.get("status") or "unknown"),
            source=str(raw.get("source") or "manual"),
            notes=str(raw.get("notes") or ""),
        ),
        [],
    )


def _default_manual_bills_path() -> Path:
    env_path = os.environ.get("AI_LAB_BILLS_PATH")
    if env_path:
        return Path(env_path)
    from brain.live_work_orchestration.builders import live_work_dir

    return live_work_dir() / "manual_bills.json"


def load_manual_bills(path: str | Path | None = None) -> list[dict[str, Any]]:
    p = Path(path) if path is not None else _default_manual_bills_path()
    if not p.is_file():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    rows = data.get("bills") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def build_bill_clarification(record: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "message": f"Clarify bill '{record.get('name') or record.get('title') or 'unknown'}': {reason}",
        "reason": reason,
        "target_list": "Agent Bills",
        "source": "bills_ingestion",
        "evidence": [str(record.get("source") or "manual")],
    }


def summarize_bills_for_planning(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    rows = []
    if isinstance(snapshot, dict):
        data = snapshot.get("data")
        rows = data if isinstance(data, list) else []
    upcoming = [r for r in rows if isinstance(r, dict) and r.get("timing_status") == "upcoming"]
    overdue = [r for r in rows if isinstance(r, dict) and r.get("status") == "overdue"]
    high_risk = [r for r in rows if isinstance(r, dict) and r.get("timing_status") == "at_risk"]
    warnings: list[str] = []
    if overdue:
        warnings.append(f"{len(overdue)} bill(s) overdue")
    if high_risk:
        warnings.append(f"{len(high_risk)} bill(s) due soon or at risk")
    return {
        "upcoming": upcoming,
        "overdue": overdue,
        "high_risk": high_risk,
        "warnings": warnings,
        "clarifications": list((snapshot or {}).get("suggested_questions") or []) if isinstance(snapshot, dict) else [],
    }


def build_bills_snapshot(path: str | Path | None = None) -> dict[str, Any]:
    raw_rows = load_manual_bills(path)
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    clarifications: list[dict[str, Any]] = []
    for raw in raw_rows:
        rec, rec_errors = validate_bill_record(raw)
        if rec is None:
            errors.extend(rec_errors)
            clarifications.append(build_bill_clarification(raw, ", ".join(rec_errors)))
            continue
        row = asdict(rec)
        row.update(evaluate_bill_status(rec))
        rows.append(row)
    snapshot = {
        "snapshot_type": "bills_snapshot",
        "generated_at": now_iso(),
        "stale": False,
        "confidence": 0.72 if rows else 0.45,
        "source_files_or_tools": [str(Path(path) if path else _default_manual_bills_path())],
        "missing_sources": [] if raw_rows else ["manual_bills"],
        "errors": errors,
        "data": rows,
        "summary_short": f"Bills: {len(rows)} explicit record(s)",
        "summary_detailed": "Manual/read-only bills snapshot; no payments, bank actions, or inferred amounts.",
        "evidence_items": [],
        "suggested_questions": clarifications,
    }
    from brain.live_work_orchestration.builders import live_work_dir

    out_dir = live_work_dir() / "ingestion"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "bills_snapshot.json").write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return snapshot
