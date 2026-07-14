"""
ClickUp action and clarification queues (local JSON). No ClickUp API execution.

All writes are to repo-local state files; execution happens only after external approval flows.

NOTE: single-writer assumption (Phase 10). This module does not implement cross-process locking.
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

from brain.prepared_context.schema import now_iso


def _live_work_dir() -> Path:
    """Use ``builders.live_work_dir()`` when available so tests can monkeypatch one root."""
    try:
        from brain.live_work_orchestration.builders import live_work_dir as _root

        d = _root()
    except Exception:
        root = Path(__file__).resolve().parents[2]
        d = root / "state" / "live_work_orchestration"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(name: str) -> Path:
    return _live_work_dir() / name


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return default
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"ClickUp queue file is corrupt: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"ClickUp queue file must contain a JSON object: {path}")
    return data


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, indent=2, default=str)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(body, encoding="utf-8")
    tmp.replace(path)


def _append_clickup_log(event_type: str, payload: dict[str, Any]) -> None:
    row = {"event_type": event_type, "at": now_iso(), "payload": payload}
    lp = _path("clickup_action_log.jsonl")
    with lp.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()


# --- Action queue (task_create | task_update | comment | status_update) ---


def _action_queue() -> dict[str, Any]:
    return _load_json(_path("clickup_action_queue.json"), {"generated_at": now_iso(), "items": []})


def _save_action_queue(data: dict[str, Any]) -> None:
    data["generated_at"] = now_iso()
    _save_json(_path("clickup_action_queue.json"), data)
    _append_clickup_log(
        "action_queue_persisted",
        {"items_count": len(list(data.get("items") or [])), "queue_file": "clickup_action_queue.json"},
    )


def queue_clickup_action(
    *,
    action_type: str,
    target_list: str,
    target_task_id: str | None,
    title: str,
    message: str,
    category: str,
    reason: str,
    source: str = "live_work",
    evidence: list[str] | None = None,
    approval_required: bool = True,
    status: str = "queued",
) -> dict[str, Any]:
    data = _action_queue()
    items = list(data.get("items") or [])
    item: dict[str, Any] = {
        "id": f"cu-{uuid.uuid4().hex[:12]}",
        "type": action_type,
        "target_list": target_list,
        "target_task_id": target_task_id,
        "title": title,
        "message": message,
        "category": category,
        "reason": reason,
        "status": status,
        "approval_required": bool(approval_required),
        "created_at": now_iso(),
        "source": source,
        "evidence": list(evidence or []),
    }
    items.append(item)
    data["items"] = items
    _save_action_queue(data)
    _append_clickup_log("queued_clickup_action", item)
    return item


def list_clickup_actions(*, statuses: tuple[str, ...] | None = None) -> list[dict[str, Any]]:
    items = list((_action_queue().get("items") or []))
    if statuses is None:
        return items
    return [x for x in items if str(x.get("status")) in statuses]


def get_action_queue_document() -> dict[str, Any]:
    """Return the persisted action queue envelope (read-only, for snapshots)."""
    return _action_queue()


# --- One-question clarification queue (Agent Clarifications list only) ---


def _clar_queue() -> dict[str, Any]:
    return _load_json(_path("clickup_clarification_queue.json"), {"generated_at": now_iso(), "items": []})


def _save_clar_queue(data: dict[str, Any]) -> None:
    data["generated_at"] = now_iso()
    _save_json(_path("clickup_clarification_queue.json"), data)
    _append_clickup_log(
        "clarification_queue_persisted",
        {"items_count": len(list(data.get("items") or [])), "queue_file": "clickup_clarification_queue.json"},
    )


def _activate_next_clarification(items: list[dict[str, Any]]) -> None:
    if any(x.get("status") == "active" for x in items):
        return
    nxt = next((x for x in items if x.get("status") == "queued"), None)
    if nxt:
        nxt["status"] = "active"
        nxt["activated_at"] = now_iso()


def queue_clarification(
    *,
    message: str,
    reason: str,
    source: str = "live_work",
    evidence: list[str] | None = None,
    target_list: str = "Agent Clarifications",
) -> dict[str, Any]:
    """Enqueue a clarification; at most one item may be ``active``."""
    data = _clar_queue()
    items = list(data.get("items") or [])
    item: dict[str, Any] = {
        "id": f"cl-{uuid.uuid4().hex[:12]}",
        "message": message,
        "target_list": target_list,
        "reason": reason,
        "status": "queued",
        "created_at": now_iso(),
        "source": source,
        "evidence": list(evidence or []),
    }
    items.append(item)
    _activate_next_clarification(items)
    data["items"] = items
    _save_clar_queue(data)
    _append_clickup_log("queued_clarification", item)
    return item


def list_clarification_items() -> list[dict[str, Any]]:
    return list((_clar_queue().get("items") or []))


def get_active_clarification() -> dict[str, Any] | None:
    items = list_clarification_items()
    return next((x for x in items if x.get("status") == "active"), None)


def promote_next_clarification() -> dict[str, Any] | None:
    """If nothing is active, promote the next ``queued`` clarification to ``active``."""
    data = _clar_queue()
    items = list(data.get("items") or [])
    _activate_next_clarification(items)
    data["items"] = items
    _save_clar_queue(data)
    return get_active_clarification()


def resolve_clarification(item_id: str) -> dict[str, Any] | None:
    """Resolve a queued or active clarification and promote the next."""
    data = _clar_queue()
    items = list(data.get("items") or [])
    target: dict[str, Any] | None = None
    for x in items:
        if x.get("id") == item_id and x.get("status") in ("queued", "active"):
            x["status"] = "resolved"
            x["resolved_at"] = now_iso()
            target = x
            break
    _activate_next_clarification(items)
    data["items"] = items
    _save_clar_queue(data)
    if target:
        _append_clickup_log("clarification_resolved", target)
    return target
