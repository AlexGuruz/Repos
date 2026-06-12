"""File-backed permanent approval rules for narrowly scoped auto-approval.

Rules are runtime state, not policy source. They only match when every saved
match field exactly equals the current approval payload subset.
"""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AI_LAB_ROOT = Path(__file__).resolve().parents[1]
PERMANENT_ALLOWLIST_PATH = AI_LAB_ROOT / "logs" / "approval_logs" / "permanent_allowlist.json"

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

_LOCK = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_action(action: str | None) -> str:
    return str(action or "").strip()


def _string_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def _clean_match(match: dict[str, Any] | None) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in dict(match or {}).items():
        k = str(key).strip()
        if not k or value is None:
            continue
        v = _string_value(value)
        if v:
            cleaned[k] = v
    return cleaned


def _load_rules_unlocked() -> list[dict[str, Any]]:
    try:
        with open(PERMANENT_ALLOWLIST_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return []
    except (OSError, json.JSONDecodeError):
        # Fail closed: bad local state should never create an auto-approval.
        return []
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if isinstance(data, dict):
        rules = data.get("rules", [])
        if isinstance(rules, list):
            return [r for r in rules if isinstance(r, dict)]
    return []


def _save_rules_unlocked(rules: list[dict[str, Any]]) -> None:
    PERMANENT_ALLOWLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PERMANENT_ALLOWLIST_PATH.with_suffix(PERMANENT_ALLOWLIST_PATH.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"version": 1, "rules": rules}, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, PERMANENT_ALLOWLIST_PATH)


def list_rules() -> list[dict[str, Any]]:
    """Return saved permanent approval rules."""
    with _LOCK:
        return [dict(rule) for rule in _load_rules_unlocked()]


def add_rule(
    action: str,
    match: dict[str, Any] | None,
    *,
    note: str = "",
    source_approval_id: str | None = None,
) -> dict[str, Any]:
    """Create a permanent approval rule for an action and exact match payload."""
    normalized_action = _clean_action(action)
    if not normalized_action:
        raise ValueError("action is required")
    if normalized_action in NEVER_PERMANENT_ACTIONS:
        raise ValueError(f"action cannot be permanently allowlisted: {normalized_action}")
    cleaned_match = _clean_match(match)
    if not cleaned_match:
        raise ValueError("match must include at least one scoped field")

    rule = {
        "id": f"PAR-{uuid.uuid4().hex[:8].upper()}",
        "action": normalized_action,
        "match": cleaned_match,
        "note": str(note or "").strip(),
        "source_approval_id": str(source_approval_id or "").strip() or None,
        "created_at": _now(),
    }
    with _LOCK:
        rules = _load_rules_unlocked()
        rules.append(rule)
        _save_rules_unlocked(rules)
    return dict(rule)


def delete_rule(rule_id: str) -> bool:
    """Delete a saved rule by id. Returns True when a rule was removed."""
    rid = str(rule_id or "").strip()
    if not rid:
        return False
    with _LOCK:
        rules = _load_rules_unlocked()
        kept = [rule for rule in rules if str(rule.get("id") or "") != rid]
        if len(kept) == len(rules):
            return False
        _save_rules_unlocked(kept)
        return True


def approval_payload_subset(payload: dict[str, Any] | None) -> dict[str, str]:
    """Return only stable fields suitable for exact permanent-rule matching."""
    data = dict(payload or {})
    return _clean_match({key: data.get(key) for key in PAYLOAD_MATCH_KEYS})


def brain_spec_match_payload(spec: dict[str, Any] | None) -> dict[str, str]:
    """Build a stable match payload from an approval queue row or approval event."""
    data = dict(spec or {})
    payload = dict(data.get("payload") or {}) if isinstance(data.get("payload"), dict) else {}
    for key in PAYLOAD_MATCH_KEYS:
        if key in data and key not in payload:
            payload[key] = data[key]
    action = data.get("action_type") or data.get("action")
    if action and "action_type" not in payload:
        payload["action_type"] = action
    return approval_payload_subset(payload)


def find_matching_rule(action: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the first exact matching permanent rule, or None."""
    normalized_action = _clean_action(action)
    if not normalized_action or normalized_action in NEVER_PERMANENT_ACTIONS:
        return None
    current = _clean_match(payload)
    if not current:
        return None
    with _LOCK:
        rules = _load_rules_unlocked()
    for rule in rules:
        if _clean_action(rule.get("action")) != normalized_action:
            continue
        expected = _clean_match(rule.get("match") if isinstance(rule.get("match"), dict) else {})
        if expected and all(current.get(key) == value for key, value in expected.items()):
            return dict(rule)
    return None
