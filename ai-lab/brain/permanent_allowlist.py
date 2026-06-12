"""
Persistent permanent approval rules for scoped, repeatable actions.

Rules are intentionally narrow: a rule must name an action and at least one
stable payload field, and all stored fields must match the candidate payload.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parents[1]
_store_dir = _root / "logs" / "approval_logs"
_store_path = _store_dir / "permanent_allowlist.json"

PAYLOAD_MATCH_KEYS = (
    "repo_id",
    "repo_path",
    "file_path",
    "path",
    "target",
    "script_path",
    "tool_name",
    "action_type",
    "reason",
)

NEVER_PERMANENT_ACTIONS = frozenset({"restart_service", "modify_registry"})
_PATH_KEYS = frozenset({"repo_path", "file_path", "path", "target", "script_path"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_value(value: Any) -> str:
    return str(value).strip()


def _normalize_pathish(value: Any) -> str:
    text = _clean_value(value).replace("\\", "/")
    while "//" in text:
        text = text.replace("//", "/")
    return text.rstrip("/") if len(text) > 1 else text


def _normalize_match(match: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in PAYLOAD_MATCH_KEYS:
        if key not in match:
            continue
        raw = match.get(key)
        if raw is None:
            continue
        value = _normalize_pathish(raw) if key in _PATH_KEYS else _clean_value(raw)
        if value:
            out[key] = value[:500]
    return out


def approval_payload_subset(payload: dict[str, Any] | None) -> dict[str, str]:
    """Return the stable, non-empty payload fields safe for rule matching."""
    return _normalize_match(dict(payload or {}))


def brain_spec_match_payload(spec: dict[str, Any] | None) -> dict[str, str]:
    """Extract a permanent-rule match payload from a brain approval row."""
    row = dict(spec or {})
    payload: dict[str, Any] = {}
    for key in PAYLOAD_MATCH_KEYS:
        if key in row:
            payload[key] = row.get(key)
    if "action_type" not in payload and row.get("action"):
        payload["action_type"] = row.get("action")
    if "reason" not in payload and row.get("detail"):
        payload["reason"] = row.get("detail")
    return approval_payload_subset(payload)


def _load_rules() -> list[dict[str, Any]]:
    if not _store_path.exists():
        return []
    try:
        data = json.loads(_store_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if isinstance(data, dict):
        data = data.get("rules", [])
    return [r for r in data if isinstance(r, dict)]


def _save_rules(rules: list[dict[str, Any]]) -> None:
    _store_dir.mkdir(parents=True, exist_ok=True)
    _store_path.write_text(json.dumps({"rules": rules}, indent=2), encoding="utf-8")


def list_rules() -> list[dict[str, Any]]:
    return _load_rules()


def add_rule(
    action: str,
    match: dict[str, Any],
    *,
    note: str = "",
    source_approval_id: str | None = None,
) -> dict[str, Any]:
    action_name = _clean_value(action)
    if not action_name:
        raise ValueError("action is required.")
    if action_name in NEVER_PERMANENT_ACTIONS:
        raise ValueError(f"'{action_name}' cannot be permanently allowlisted.")

    normalized = approval_payload_subset(match)
    if not normalized:
        raise ValueError("match must include at least one scoped payload field.")

    rules = _load_rules()
    for existing in rules:
        if existing.get("action") == action_name and existing.get("match") == normalized:
            return existing

    rule = {
        "id": f"PAR-{uuid.uuid4().hex[:8].upper()}",
        "action": action_name,
        "match": normalized,
        "note": _clean_value(note)[:500],
        "source_approval_id": _clean_value(source_approval_id)[:120] if source_approval_id else None,
        "created_at": _now(),
    }
    rules.append(rule)
    _save_rules(rules)
    return rule


def delete_rule(rule_id: str) -> bool:
    rid = _clean_value(rule_id)
    rules = _load_rules()
    kept = [r for r in rules if r.get("id") != rid]
    if len(kept) == len(rules):
        return False
    _save_rules(kept)
    return True


def find_matching_rule(action: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    action_name = _clean_value(action)
    if not action_name or action_name in NEVER_PERMANENT_ACTIONS:
        return None

    candidate = approval_payload_subset(payload)
    if not candidate:
        return None

    for rule in _load_rules():
        if rule.get("action") != action_name:
            continue
        rule_match = approval_payload_subset(rule.get("match") if isinstance(rule.get("match"), dict) else {})
        if not rule_match:
            continue
        if all(candidate.get(key) == value for key, value in rule_match.items()):
            return rule
    return None
