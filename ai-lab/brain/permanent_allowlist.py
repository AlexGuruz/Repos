"""Persistent, scoped permanent approval rules.

Rules are exact-match only: every stored match key must equal the incoming
approval payload. This keeps permanent approvals narrow enough for controlled
operations while allowing repeated, identical requests to skip the approval card.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_ROOT = Path(__file__).resolve().parents[1]
_RULES_PATH = _ROOT / "memory" / "permanent_approval_rules.json"

NEVER_PERMANENT_ACTIONS = frozenset({"restart_service", "modify_registry"})

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
    "detail",
)


def _clean_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def _normalize_match(match: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(match, dict):
        return {}
    out: dict[str, str] = {}
    for key in PAYLOAD_MATCH_KEYS:
        value = _clean_value(match.get(key))
        if value:
            out[key] = value
    return out


def _load_rules() -> list[dict[str, Any]]:
    if not _RULES_PATH.is_file():
        return []
    try:
        with _RULES_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def _save_rules(rules: list[dict[str, Any]]) -> None:
    _RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _RULES_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)
        f.write("\n")
    tmp.replace(_RULES_PATH)


def list_rules() -> list[dict[str, Any]]:
    """Return stored permanent approval rules."""
    return _load_rules()


def approval_payload_subset(payload: dict[str, Any] | None) -> dict[str, str]:
    """Extract the safe subset of fields used for permanent-rule matching."""
    return _normalize_match(payload)


def brain_spec_match_payload(spec: dict[str, Any] | None) -> dict[str, str]:
    """Build a match payload from a brain approval-queue row or API payload."""
    if not isinstance(spec, dict):
        return {}
    merged: dict[str, Any] = {}
    for nested_key in ("payload", "args", "supervisor_payload"):
        nested = spec.get(nested_key)
        if isinstance(nested, dict):
            merged.update(nested)
    for key in PAYLOAD_MATCH_KEYS:
        if spec.get(key) is not None:
            merged[key] = spec[key]
    if spec.get("action") and not merged.get("action_type"):
        merged["action_type"] = spec["action"]
    return approval_payload_subset(merged)


def find_matching_rule(action: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the first enabled rule whose action and scoped fields match exactly."""
    wanted_action = _clean_value(action)
    if not wanted_action:
        return None
    candidate = approval_payload_subset(payload)
    for rule in _load_rules():
        if rule.get("enabled") is False:
            continue
        if _clean_value(rule.get("action")) != wanted_action:
            continue
        match = _normalize_match(rule.get("match"))
        if match and all(candidate.get(key) == value for key, value in match.items()):
            return rule
    return None


def add_rule(
    action: str,
    match: dict[str, Any] | None,
    *,
    note: str = "",
    source_approval_id: str | None = None,
) -> dict[str, Any]:
    """Create a scoped permanent approval rule, or return an existing duplicate."""
    clean_action = _clean_value(action)
    if not clean_action:
        raise ValueError("action is required")
    if clean_action in NEVER_PERMANENT_ACTIONS:
        raise ValueError(f"action '{clean_action}' cannot be permanently allowlisted")
    clean_match = _normalize_match(match)
    if not clean_match:
        raise ValueError("at least one supported match field is required")

    rules = _load_rules()
    for rule in rules:
        if _clean_value(rule.get("action")) == clean_action and _normalize_match(rule.get("match")) == clean_match:
            return rule

    existing_ids = {_clean_value(rule.get("id")) for rule in rules}
    rule_id = f"PAR-{uuid.uuid4().hex[:8].upper()}"
    while rule_id in existing_ids:
        rule_id = f"PAR-{uuid.uuid4().hex[:8].upper()}"
    rule = {
        "id": rule_id,
        "action": clean_action,
        "match": clean_match,
        "note": _clean_value(note),
        "source_approval_id": _clean_value(source_approval_id),
        "enabled": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    rules.append(rule)
    _save_rules(rules)
    return rule


def delete_rule(rule_id: str) -> bool:
    """Delete a permanent approval rule by id."""
    rid = _clean_value(rule_id)
    rules = _load_rules()
    remaining = [rule for rule in rules if _clean_value(rule.get("id")) != rid]
    if len(remaining) == len(rules):
        return False
    _save_rules(remaining)
    return True
