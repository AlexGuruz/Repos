"""
Approval queue: submit(spec) -> id, list_pending(), resolve(id, approve).
Persists to logs/approval_logs/pending.json; logs resolved to approval_logs/.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone
from typing import Any

_root = Path(__file__).resolve().parents[2]
_log_dir = _root / "logs" / "approval_logs"
_pending_path = _log_dir / "pending.json"


def _maybe_attach_catalog_context(row: dict[str, Any]) -> None:
    if row.get("catalog_context") or not row.get("file_path"):
        return
    try:
        from brain.catalog_loader import format_approval_catalog_attachment

        ctx = format_approval_catalog_attachment(str(row["file_path"]))
        if ctx:
            row["catalog_context"] = ctx
    except Exception:
        pass


@dataclass
class ApprovalSpec:
    file_path: str
    action_type: str
    reason: str
    diff_preview: str | None = None
    risk_level: str = "medium"
    # Optional: lines from system catalog (governance) for grounded review UI
    catalog_context: str | None = None


def _load_pending() -> dict[str, dict]:
    _log_dir.mkdir(parents=True, exist_ok=True)
    if not _pending_path.exists():
        return {}
    with open(_pending_path) as f:
        return json.load(f)


def _save_pending(pending: dict) -> None:
    _log_dir.mkdir(parents=True, exist_ok=True)
    with open(_pending_path, "w") as f:
        json.dump(pending, f, indent=2)


def _log_resolved(id_: str, spec: dict, approve: bool) -> None:
    path = _log_dir / f"resolved_{id_.replace('-', '_')}.json"
    with open(path, "w") as f:
        json.dump({
            "id": id_,
            "spec": spec,
            "approved": approve,
            "at": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2)


def submit(spec: ApprovalSpec | dict[str, Any]) -> str:
    """Enqueue approval request; return id."""
    pending = _load_pending()
    next_id = len(pending) + 1
    id_ = f"approval-{next_id}"
    if isinstance(spec, ApprovalSpec):
        row = {
            "file_path": spec.file_path,
            "action_type": spec.action_type,
            "reason": spec.reason,
            "diff_preview": spec.diff_preview,
            "risk_level": spec.risk_level,
            "catalog_context": spec.catalog_context,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        _maybe_attach_catalog_context(row)
        pending[id_] = row
    else:
        spec_dict = dict(spec)
        spec_dict.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        _maybe_attach_catalog_context(spec_dict)
        pending[id_] = spec_dict
    _save_pending(pending)
    return id_


def list_pending() -> list[tuple[str, dict[str, Any]]]:
    """Return list of (id, spec) for pending approvals."""
    return list(_load_pending().items())


def resolve(id_: str, approve: bool) -> bool:
    """Resolve approval by id; log to approval_logs. Return True if id existed."""
    pending = _load_pending()
    if id_ not in pending:
        return False
    spec = pending.pop(id_)
    _log_resolved(id_, spec, approve)
    _save_pending(pending)
    return True
