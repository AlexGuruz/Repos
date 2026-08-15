from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class BillRecord:
    name: str
    due_date: str = ""
    amount: float | None = None
    currency: str = "USD"
    status: str = "open"
    source: str = "manual"
    notes: str = ""
    days_until_due: int | None = None
    timing_status: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _state_root() -> Path:
    try:
        from brain.live_work_orchestration.builders import live_work_dir

        return live_work_dir()
    except Exception:
        pass
    return Path(__file__).resolve().parents[3] / "state" / "live_work_orchestration"


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except Exception:
        return None


def evaluate_bill_status(raw: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    """Return conservative timing status for an explicit manual bill row."""
    today = today or datetime.now(timezone.utc).date()
    due = _parse_date(raw.get("due_date"))
    status = str(raw.get("status") or "open").strip().lower() or "open"
    out = dict(raw)
    if status in ("paid", "done", "closed"):
        out["status"] = "paid"
        out["timing_status"] = "paid"
        out["days_until_due"] = None
        return out
    if due is None:
        out["status"] = status
        out["timing_status"] = "unknown"
        out["days_until_due"] = None
        return out
    days = (due - today).days
    out["days_until_due"] = days
    if days < 0:
        out["status"] = "overdue"
        out["timing_status"] = "overdue"
    elif days <= 3:
        out["status"] = status
        out["timing_status"] = "at_risk"
    elif days <= 14:
        out["status"] = status
        out["timing_status"] = "upcoming"
    else:
        out["status"] = status
        out["timing_status"] = "future"
    return out


def validate_bill_record(raw: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not str(raw.get("name") or "").strip():
        errors.append("missing name")
    if raw.get("amount") not in (None, ""):
        try:
            float(raw.get("amount"))
        except Exception:
            errors.append("invalid amount")
    if raw.get("due_date") and _parse_date(raw.get("due_date")) is None:
        errors.append("invalid due_date")
    return not errors, errors


def load_manual_bills(path: str | Path | None = None) -> list[dict[str, Any]]:
    """Load explicit local bill rows; missing files mean no bill data, not an error."""
    raw_path = path or os.environ.get("LIVE_WORK_BILLS_PATH") or (_state_root() / "manual_bills.json")
    p = Path(raw_path)
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = data.get("bills") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def build_bill_clarification(raw: dict[str, Any], errors: list[str] | None = None) -> dict[str, Any]:
    return {
        "message": f"Clarify bill details for {raw.get('name') or 'unnamed bill'}",
        "reason": "; ".join(errors or ["missing_or_conflicting_bill_fields"]),
        "target_list": "Agent Bills",
        "source": "bills_ingestion",
        "evidence": [str(raw.get("source") or "manual")],
    }


def build_bills_snapshot(path: str | Path | None = None) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    clarifications: list[dict[str, Any]] = []
    for raw in load_manual_bills(path):
        ok, errors = validate_bill_record(raw)
        if not ok:
            clarifications.append(build_bill_clarification(raw, errors))
            continue
        evaluated = evaluate_bill_status(raw)
        rec = BillRecord(
            name=str(evaluated.get("name") or "").strip(),
            due_date=str(evaluated.get("due_date") or "").strip(),
            amount=float(evaluated["amount"]) if evaluated.get("amount") not in (None, "") else None,
            currency=str(evaluated.get("currency") or "USD"),
            status=str(evaluated.get("status") or "open"),
            source=str(evaluated.get("source") or "manual"),
            notes=str(evaluated.get("notes") or ""),
            days_until_due=evaluated.get("days_until_due"),
            timing_status=str(evaluated.get("timing_status") or "unknown"),
        )
        rows.append(rec.to_dict())

    snap = {
        "snapshot_type": "bills_snapshot",
        "generated_at": _now_iso(),
        "stale": False,
        "confidence": 0.8 if rows else 0.35,
        "source_files_or_tools": [str(path or os.environ.get("LIVE_WORK_BILLS_PATH") or "manual_bills.json")],
        "missing_sources": [] if rows else ["manual_bills"],
        "errors": [],
        "data": rows,
        "summary_short": f"Bills: {len(rows)} explicit row(s)",
        "summary_detailed": "Manual bills only; no bank APIs, payment actions, or invented amounts.",
        "clarifications": clarifications,
    }
    out_dir = _state_root() / "ingestion"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "bills_snapshot.json").write_text(json.dumps(snap, indent=2), encoding="utf-8")
    return snap


def summarize_bills_for_planning(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    data = (snapshot or {}).get("data") if isinstance(snapshot, dict) else []
    rows = data.get("bills") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        rows = []
    bill_rows = [r for r in rows if isinstance(r, dict)]
    overdue = [r for r in bill_rows if r.get("status") == "overdue" or r.get("timing_status") == "overdue"]
    upcoming = [r for r in bill_rows if r.get("timing_status") == "upcoming"]
    high_risk = [r for r in bill_rows if r.get("timing_status") in ("overdue", "at_risk")]
    clarifications = list((snapshot or {}).get("clarifications") or []) if isinstance(snapshot, dict) else []
    warnings = [
        f"{r.get('name')} is {r.get('timing_status')}"
        for r in high_risk[:5]
        if r.get("name")
    ]
    return {
        "upcoming": upcoming,
        "overdue": overdue,
        "high_risk": high_risk,
        "warnings": warnings,
        "clarifications": clarifications,
    }


__all__ = [
    "BillRecord",
    "build_bill_clarification",
    "build_bills_snapshot",
    "evaluate_bill_status",
    "load_manual_bills",
    "summarize_bills_for_planning",
    "validate_bill_record",
]
