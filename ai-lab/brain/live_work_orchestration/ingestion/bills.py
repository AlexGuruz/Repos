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
    due_date: str | None = None
    amount: float | None = None
    currency: str = "USD"
    status: str = "unknown"
    timing_status: str = "unknown"
    days_until_due: int | None = None
    evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _root() -> Path:
    return Path(__file__).resolve().parents[3]


def _ingestion_dir() -> Path:
    from brain.live_work_orchestration.builders import live_work_dir

    return live_work_dir() / "ingestion"


def _parse_due_date(raw: Any) -> date | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        pass
    try:
        return date.fromisoformat(text[:10])
    except Exception:
        return None


def evaluate_bill_status(row: dict[str, Any], *, today: date | None = None) -> dict[str, Any]:
    today = today or datetime.now(timezone.utc).date()
    due = _parse_due_date(row.get("due_date"))
    paid = str(row.get("status") or "").strip().lower() in ("paid", "done", "complete", "completed")
    if due is None:
        return {"status": "unknown", "timing_status": "unknown", "days_until_due": None}
    days = (due - today).days
    if paid:
        status = "paid"
        timing = "ok"
    elif days < 0:
        status = "overdue"
        timing = "at_risk"
    elif days <= 7:
        status = "due_soon"
        timing = "at_risk"
    elif days <= 30:
        status = "upcoming"
        timing = "upcoming"
    else:
        status = "open"
        timing = "ok"
    return {"status": status, "timing_status": timing, "days_until_due": days}


def validate_bill_record(row: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not str(row.get("name") or "").strip():
        errors.append("missing name")
    amount = row.get("amount")
    if amount not in (None, ""):
        try:
            if float(amount) < 0:
                errors.append("amount must be non-negative")
        except Exception:
            errors.append("amount must be numeric")
    if row.get("due_date") and _parse_due_date(row.get("due_date")) is None:
        errors.append("due_date must be ISO-like")
    return len(errors) == 0, errors


def _load_json_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        rows = payload.get("bills") or payload.get("items") or payload.get("data")
        if isinstance(rows, list):
            return [r for r in rows if isinstance(r, dict)]
    return []


def load_manual_bills(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    lane = (config or {}).get("bills") if isinstance(config, dict) else None
    paths: list[Path] = []
    if isinstance(lane, dict):
        raw_paths = lane.get("files") or lane.get("manual_files") or []
        if isinstance(raw_paths, str):
            raw_paths = [raw_paths]
        for raw in raw_paths:
            p = Path(str(raw)).expanduser()
            paths.append(p if p.is_absolute() else _root() / p)
    if not paths:
        paths = [_root() / "config" / "manual_bills.json"]

    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.extend(_load_json_rows(path))
    return rows


def build_bill_clarification(row: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "message": f"Confirm bill details for {row.get('name') or 'unnamed bill'}: {reason}.",
        "reason": reason,
        "source": "bills_ingestion",
        "evidence": [str(row.get("name") or ""), str(row.get("due_date") or "")],
        "target_list": "Agent Clarifications",
    }


def _normalize_bill(row: dict[str, Any]) -> BillRecord:
    status = evaluate_bill_status(row)
    warnings: list[str] = []
    ok, errors = validate_bill_record(row)
    if not ok:
        warnings.extend(errors)
    amount: float | None
    try:
        amount = float(row.get("amount")) if row.get("amount") not in (None, "") else None
    except Exception:
        amount = None
    return BillRecord(
        name=str(row.get("name") or row.get("title") or "Unnamed bill").strip(),
        due_date=str(row.get("due_date") or "").strip() or None,
        amount=amount,
        currency=str(row.get("currency") or "USD").strip() or "USD",
        status=str(status["status"]),
        timing_status=str(status["timing_status"]),
        days_until_due=status["days_until_due"],
        evidence=[str(x) for x in (row.get("evidence") or [])],
        warnings=warnings,
    )


def summarize_bills_for_planning(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    rows = []
    if isinstance(snapshot, dict):
        data = snapshot.get("data")
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            rows = data.get("bills") or data.get("items") or []
    bill_rows = [r for r in rows if isinstance(r, dict)]
    warnings: list[str] = []
    clarifications: list[dict[str, Any]] = []
    for row in bill_rows:
        if row.get("status") == "overdue":
            warnings.append(f"Overdue bill: {row.get('name')} due {row.get('due_date')}")
        elif row.get("timing_status") == "at_risk":
            warnings.append(f"Bill due soon: {row.get('name')} due {row.get('due_date')}")
        for warn in row.get("warnings") or []:
            clarifications.append(build_bill_clarification(row, str(warn)))
    return {
        "total_count": len(bill_rows),
        "overdue_count": len([r for r in bill_rows if r.get("status") == "overdue"]),
        "at_risk_count": len([r for r in bill_rows if r.get("timing_status") == "at_risk"]),
        "warnings": warnings,
        "clarifications": clarifications,
    }


def build_bills_snapshot(config: dict[str, Any] | None = None) -> dict[str, Any]:
    raw_rows = load_manual_bills(config)
    bills = [_normalize_bill(row).to_dict() for row in raw_rows]
    missing = [] if raw_rows else ["manual_bills"]
    snap = {
        "snapshot_type": "bills_snapshot",
        "generated_at": now_iso(),
        "freshness_seconds": 3600,
        "source_files_or_tools": ["config/manual_bills.json"],
        "confidence": 0.75 if raw_rows else 0.35,
        "stale": False,
        "errors": [],
        "data": bills,
        "missing_sources": missing,
        "summary_short": f"Bills tracked: {len(bills)}",
        "summary_detailed": "Manual bill snapshot only; no bank, card, calendar, or ClickUp writes.",
        "suggested_questions": [],
        "evidence_items": [{"source": "manual_bills", "summary": f"{len(bills)} row(s) loaded"}],
    }
    out = _ingestion_dir() / "bills_snapshot.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".tmp")
    tmp.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    tmp.replace(out)
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
