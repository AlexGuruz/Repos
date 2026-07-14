"""Manual-first bills ingestion for live-work planning.

This lane only reads explicit local records. It does not connect to banks,
initiate payments, or invent amounts/dates when inputs are missing.
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
    due_date: str | None = None
    amount: float | None = None
    currency: str = "USD"
    status: str = "unknown"
    category: str = "agent_bills"
    source: str = "manual"
    evidence: list[str] | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        out["evidence"] = list(self.evidence or [])
        return out


def _ingestion_dir() -> Path:
    root = Path(__file__).resolve().parents[3]
    d = root / "state" / "live_work_orchestration" / "ingestion"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except Exception:
        try:
            return date.fromisoformat(str(value)[:10])
        except Exception:
            return None


def _today() -> date:
    return datetime.now(timezone.utc).date()


def _coerce_amount(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return round(float(value), 2)
    except Exception:
        return None


def validate_bill_record(record: dict[str, Any] | BillRecord) -> tuple[bool, list[str]]:
    row = record.to_dict() if isinstance(record, BillRecord) else dict(record or {})
    errors: list[str] = []
    if not str(row.get("name") or "").strip():
        errors.append("missing_name")
    if row.get("due_date") and _parse_date(str(row.get("due_date"))) is None:
        errors.append("invalid_due_date")
    if row.get("amount") not in (None, "") and _coerce_amount(row.get("amount")) is None:
        errors.append("invalid_amount")
    return not errors, errors


def evaluate_bill_status(record: dict[str, Any] | BillRecord, *, today: date | None = None) -> dict[str, Any]:
    row = record.to_dict() if isinstance(record, BillRecord) else dict(record or {})
    today = today or _today()
    due = _parse_date(str(row.get("due_date") or "")) if row.get("due_date") else None
    explicit_status = str(row.get("status") or "unknown").strip().lower()
    if explicit_status in {"paid", "cancelled", "ignored"}:
        status = explicit_status
    elif due and due < today:
        status = "overdue"
    elif explicit_status in {"unpaid", "open", "due"}:
        status = "open"
    else:
        status = explicit_status or "unknown"

    days_until_due = (due - today).days if due else None
    if status == "overdue":
        timing_status = "at_risk"
    elif days_until_due is None:
        timing_status = "unknown"
    elif days_until_due <= 3:
        timing_status = "at_risk"
    elif days_until_due <= 14:
        timing_status = "upcoming"
    else:
        timing_status = "later"

    out = dict(row)
    out["status"] = status
    out["timing_status"] = timing_status
    out["days_until_due"] = days_until_due
    out["amount"] = _coerce_amount(row.get("amount"))
    out["currency"] = str(row.get("currency") or "USD")
    out["evidence"] = list(row.get("evidence") or [])
    return out


def build_bill_clarification(record: dict[str, Any]) -> dict[str, Any] | None:
    missing: list[str] = []
    if not str(record.get("name") or "").strip():
        missing.append("name")
    if not record.get("due_date"):
        missing.append("due_date")
    if record.get("amount") is None:
        missing.append("amount")
    if not missing:
        return None
    name = str(record.get("name") or "unnamed bill")
    return {
        "target_list": "Agent Bills",
        "message": f"Clarify {', '.join(missing)} for bill '{name}' before using it as a planning constraint.",
        "reason": "missing_bill_fields",
        "bill_name": name,
        "missing_fields": missing,
        "approval_required": True,
    }


def _manual_bills_path(config: dict[str, Any] | None = None) -> Path:
    lane = (config or {}).get("bills") if isinstance(config, dict) else None
    raw = (lane or {}).get("manual_bills_file") if isinstance(lane, dict) else None
    if raw:
        return Path(str(raw)).expanduser()
    return _ingestion_dir() / "manual_bills.json"


def load_manual_bills(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    path = _manual_bills_path(config)
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = payload.get("bills") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = evaluate_bill_status(row)
        ok, errors = validate_bill_record(normalized)
        normalized["validation_errors"] = errors
        normalized["valid"] = ok
        out.append(normalized)
    return out


def _rows_from_snapshot(snapshot: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(snapshot, dict):
        return []
    data = snapshot.get("data")
    if isinstance(data, list):
        rows = data
    elif isinstance(data, dict):
        rows = data.get("bills") or data.get("items") or []
    else:
        rows = []
    return [x for x in rows if isinstance(x, dict)]


def summarize_bills_for_planning(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    rows = [evaluate_bill_status(x) for x in _rows_from_snapshot(snapshot)]
    overdue = [x for x in rows if x.get("status") == "overdue"]
    upcoming = [x for x in rows if x.get("timing_status") in {"at_risk", "upcoming"} and x.get("status") != "paid"]
    high_risk = [x for x in rows if x.get("timing_status") == "at_risk" and x.get("status") != "paid"]
    clarifications = [c for c in (build_bill_clarification(x) for x in rows) if c]
    warnings: list[str] = []
    if overdue:
        warnings.append(f"{len(overdue)} bill(s) overdue; verify before committing time/cash plans.")
    if high_risk:
        warnings.append(f"{len(high_risk)} bill(s) due within 3 days or overdue.")
    return {
        "total": len(rows),
        "upcoming": upcoming,
        "overdue": overdue,
        "high_risk": high_risk,
        "warnings": warnings,
        "clarifications": clarifications,
    }


def build_bills_snapshot(config: dict[str, Any] | None = None) -> dict[str, Any]:
    rows = load_manual_bills(config)
    summary = summarize_bills_for_planning({"data": {"bills": rows}})
    generated = now_iso()
    payload = {
        "snapshot_type": "bills_snapshot",
        "generated_at": generated,
        "freshness_seconds": 3600,
        "stale": False,
        "confidence": 0.8 if rows else 0.55,
        "source_files_or_tools": [str(_manual_bills_path(config))],
        "missing_sources": [] if rows else ["manual_bills"],
        "errors": [],
        "data": {"bills": rows},
        "summary_short": f"Bills: {len(rows)} manual records; {len(summary['overdue'])} overdue",
        "summary_detailed": "Manual bills only; no payment, banking, or forecasting actions are performed.",
        "evidence_items": [
            {
                "title": "Bills ingestion",
                "summary": "Loaded explicit local/manual bill records for planning constraints.",
                "source_path_or_tool": str(_manual_bills_path(config)),
                "observed_at": generated,
                "confidence": 0.8 if rows else 0.55,
            }
        ],
        "suggested_questions": [c["message"] for c in summary["clarifications"][:5]],
    }
    (_ingestion_dir() / "bills_snapshot.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return payload
