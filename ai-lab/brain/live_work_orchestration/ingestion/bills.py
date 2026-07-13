from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from brain.prepared_context.schema import now_iso


def _state_dir() -> Path:
    try:
        from brain.live_work_orchestration.builders import live_work_dir

        return live_work_dir()
    except Exception:
        root = Path(__file__).resolve().parents[3]
        return root / "state" / "live_work_orchestration"


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except Exception:
        return None


@dataclass
class BillRecord:
    name: str
    due_date: str | None = None
    amount: float | None = None
    currency: str = "USD"
    status: str = "unknown"
    timing_status: str = "unknown"
    days_until_due: int | None = None
    source: str = "manual_bills"
    notes: str = ""
    validation_warnings: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["validation_warnings"] = list(self.validation_warnings or [])
        return out


def evaluate_bill_status(row: dict[str, Any] | BillRecord, *, today: date | None = None) -> dict[str, Any]:
    data = row.to_dict() if isinstance(row, BillRecord) else dict(row)
    base_status = str(data.get("status") or "unknown").strip().lower()
    due = _parse_date(data.get("due_date"))
    today = today or datetime.now(timezone.utc).date()
    days_until_due = (due - today).days if due is not None else None

    if base_status in {"paid", "done", "settled"}:
        status = "paid"
        timing_status = "paid"
    elif days_until_due is None:
        status = "unknown"
        timing_status = "unknown"
    elif days_until_due < 0:
        status = "overdue"
        timing_status = "overdue"
    elif days_until_due <= 7:
        status = "due_soon"
        timing_status = "at_risk"
    else:
        status = base_status if base_status not in {"", "unknown"} else "upcoming"
        timing_status = "upcoming"

    data["status"] = status
    data["timing_status"] = timing_status
    data["days_until_due"] = days_until_due
    return data


def validate_bill_record(row: dict[str, Any], *, today: date | None = None) -> BillRecord:
    warnings: list[str] = []
    name = str(row.get("name") or row.get("title") or "").strip()
    if not name:
        name = "Unnamed bill"
        warnings.append("missing_name")
    due_date = str(row.get("due_date") or "").strip() or None
    if _parse_date(due_date) is None:
        warnings.append("missing_or_invalid_due_date")
        due_date = None

    amount_raw = row.get("amount")
    amount: float | None
    try:
        amount = float(amount_raw) if amount_raw not in (None, "") else None
    except Exception:
        amount = None
        warnings.append("invalid_amount")

    evaluated = evaluate_bill_status(
        {
            "status": row.get("status"),
            "due_date": due_date,
        },
        today=today,
    )
    return BillRecord(
        name=name,
        due_date=due_date,
        amount=amount,
        currency=str(row.get("currency") or "USD"),
        status=str(evaluated.get("status") or "unknown"),
        timing_status=str(evaluated.get("timing_status") or "unknown"),
        days_until_due=evaluated.get("days_until_due"),
        source=str(row.get("source") or "manual_bills"),
        notes=str(row.get("notes") or ""),
        validation_warnings=warnings,
    )


def load_manual_bills(path: str | Path | None = None) -> list[BillRecord]:
    source = Path(path) if path is not None else _state_dir() / "manual_bills.json"
    if not source.is_file():
        return []
    raw = json.loads(source.read_text(encoding="utf-8"))
    rows = raw.get("bills") if isinstance(raw, dict) else raw
    if not isinstance(rows, list):
        return []
    return [validate_bill_record(row) for row in rows if isinstance(row, dict)]


def build_bill_clarification(row: dict[str, Any] | BillRecord) -> dict[str, Any] | None:
    data = row.to_dict() if isinstance(row, BillRecord) else dict(row)
    warnings = list(data.get("validation_warnings") or [])
    if not warnings:
        return None
    return {
        "target_list": "Agent Bills",
        "source": "bills_ingestion",
        "reason": ",".join(warnings),
        "message": f"Please confirm bill details for {data.get('name')}: {', '.join(warnings)}.",
        "evidence": [str(data.get("source") or "manual_bills")],
    }


def summarize_bills_for_planning(snapshot: dict[str, Any] | None) -> dict[str, list[dict[str, Any]]]:
    rows = []
    if isinstance(snapshot, dict):
        data = snapshot.get("data")
        rows = data if isinstance(data, list) else []
    out = {
        "upcoming": [],
        "overdue": [],
        "high_risk": [],
        "warnings": [],
        "clarifications": [],
    }
    for row in rows:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "")
        timing = str(row.get("timing_status") or "")
        if status == "overdue":
            out["overdue"].append(row)
        if timing == "upcoming":
            out["upcoming"].append(row)
        if timing == "at_risk":
            out["high_risk"].append(row)
        if row.get("validation_warnings"):
            out["warnings"].append(row)
            clarification = build_bill_clarification(row)
            if clarification:
                out["clarifications"].append(clarification)
    return out


def build_bills_snapshot(path: str | Path | None = None) -> dict[str, Any]:
    bills = load_manual_bills(path)
    rows = [bill.to_dict() for bill in bills]
    summary = summarize_bills_for_planning({"data": rows})
    source = Path(path) if path is not None else _state_dir() / "manual_bills.json"
    payload = {
        "snapshot_type": "bills_snapshot",
        "generated_at": now_iso(),
        "stale": False,
        "confidence": 0.75 if source.is_file() else 0.35,
        "source_files_or_tools": [str(source)],
        "missing_sources": [] if source.is_file() else ["manual_bills_json"],
        "errors": [],
        "data": rows,
        "summary_short": (
            f"Bills: {len(summary['overdue'])} overdue, {len(summary['high_risk'])} high risk, "
            f"{len(summary['upcoming'])} upcoming"
        ),
        "summary_detailed": "Manual bill lane only; no bank/payment APIs or payment actions.",
        "evidence_items": [
            {
                "title": "Bills ingestion",
                "summary": f"{len(rows)} manual bill row(s) loaded",
                "source_path_or_tool": str(source),
                "observed_at": now_iso(),
                "confidence": 0.75 if source.is_file() else 0.35,
            }
        ],
        "suggested_questions": summary["clarifications"],
    }
    out_dir = _state_dir() / "ingestion"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "bills_snapshot.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
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
