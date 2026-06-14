"""Persistent scoped permanent approval rules.

Rules are intentionally narrow: an action matches only when every stored
match key has the same normalized value in the candidate payload.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parents[1]
_rules_path = _root / "logs" / "approval_logs" / "permanent_allowlist.json"

MATCH_KEYS = (
    "repo_id",
    "repo_path",
    "file_path",
    "path",
    "target",
    "script_path",
    "tool_name",
    "action_type",
    "reason",
    "detail",
)

NEVER_PERMANENT_ACTIONS = frozenset({"restart_service", "modify_registry"})


def _normalize_scalar(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


def _normalize_match(match: dict[str, Any]) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in MATCH_KEYS:
        if key not in match:
            continue
        value = _normalize_scalar(match.get(key))
        if value:
            out[key] = value
    return out


def _load_rules() -> list[dict[str, Any]]:
    if not _rules_path.exists():
        return []
    try:
        data = json.loads(_rules_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def _save_rules(rules: list[dict[str, Any]]) -> None:
    _rules_path.parent.mkdir(parents=True, exist_ok=True)
    _rules_path.write_text(json.dumps(rules, indent=2) + "\n", encoding="utf-8")


def approval_payload_subset(payload: dict[str, Any]) -> dict[str, str]:
    """Return the scoped fields that may be used for permanent matching."""
    return _normalize_match(payload or {})


def brain_spec_match_payload(spec: dict[str, Any]) -> dict[str, str]:
    """Build a permanent-rule match payload from an approval queue row."""
    payload = approval_payload_subset(spec or {})
    action = _normalize_scalar((spec or {}).get("action_type") or (spec or {}).get("action"))
    if action and "action_type" not in payload:
        payload["action_type"] = action
    return payload


def list_rules() -> list[dict[str, Any]]:
    return _load_rules()


def add_rule(
    action: str,
    match: dict[str, Any],
    *,
    note: str = "",
    source_approval_id: str | None = None,
) -> dict[str, Any]:
    action_name = _normalize_scalar(action)
    if not action_name:
        raise ValueError("action is required")
    if action_name in NEVER_PERMANENT_ACTIONS:
        raise ValueError(f"action '{action_name}' cannot be permanently allowlisted")
    normalized_match = _normalize_match(match or {})
    if not normalized_match:
        raise ValueError("permanent approval rules require at least one scoped match field")

    rules = _load_rules()
    rule = {
        "id": f"perm-{uuid.uuid4().hex[:8]}",
        "action": action_name,
        "match": normalized_match,
        "note": _normalize_scalar(note),
        "source_approval_id": _normalize_scalar(source_approval_id),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    rules.append(rule)
    _save_rules(rules)
    return rule


def delete_rule(rule_id: str) -> bool:
    rid = _normalize_scalar(rule_id)
    rules = _load_rules()
    kept = [rule for rule in rules if _normalize_scalar(rule.get("id")) != rid]
    if len(kept) == len(rules):
        return False
    _save_rules(kept)
    return True


def find_matching_rule(action: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    action_name = _normalize_scalar(action)
    if not action_name or action_name in NEVER_PERMANENT_ACTIONS:
        return None
    candidate = _normalize_match(payload or {})
    if not candidate:
        return None
    for rule in _load_rules():
        if _normalize_scalar(rule.get("action")) != action_name:
            continue
        match = _normalize_match(rule.get("match") or {})
        if match and all(candidate.get(key) == value for key, value in match.items()):
            return rule
    return None
