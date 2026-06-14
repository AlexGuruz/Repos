"""Persistent, narrowly-scoped permanent approval rules.

Rules are intentionally simple: an action must match exactly and every stored
match field must equal the incoming approval payload.  Broad or dangerous
actions are rejected so a UI shortcut cannot accidentally create a blanket
write approval.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_RULES_PATH = _ROOT / "memory" / "permanent_allowlist.json"

MATCH_KEYS = frozenset(
    {
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
    }
)

SCOPE_KEYS = frozenset(
    {
        "repo_id",
        "repo_path",
        "file_path",
        "path",
        "target",
        "script_path",
        "tool_name",
    }
)

NEVER_PERMANENT_ACTIONS = frozenset({"restart_service", "modify_registry"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_action(action: str | None) -> str:
    return str(action or "").strip()


def _clean_match(match: dict[str, Any] | None) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    for key, value in dict(match or {}).items():
        if key not in MATCH_KEYS or value is None:
            continue
        text = str(value).strip()
        if text:
            cleaned[key] = text
    return cleaned


def _load_rules() -> list[dict[str, Any]]:
    if not _RULES_PATH.exists():
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
    with _RULES_PATH.open("w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, sort_keys=True)
        f.write("\n")


def list_rules() -> list[dict[str, Any]]:
    """Return all permanent approval rules."""
    return _load_rules()


def approval_payload_subset(payload: dict[str, Any] | None) -> dict[str, str]:
    """Extract stable, UI-safe fields from a supervisor invoke payload."""
    return _clean_match(payload)


def brain_spec_match_payload(spec: dict[str, Any] | None) -> dict[str, str]:
    """Extract stable fields from an approval queue row."""
    row = dict(spec or {})
    out = _clean_match(row)
    args = row.get("args")
    if isinstance(args, dict):
        out.update({k: v for k, v in _clean_match(args).items() if k not in out})
    action = row.get("action_type") or row.get("action")
    if action and "action_type" not in out:
        out["action_type"] = str(action).strip()
    return {k: v for k, v in out.items() if v}


def add_rule(
    action: str,
    match: dict[str, Any] | None,
    *,
    note: str = "",
    source_approval_id: str | None = None,
) -> dict[str, Any]:
    """Create a permanent rule after validating it is scoped and safe."""
    clean_action = _normalize_action(action)
    if not clean_action:
        raise ValueError("action is required")
    if clean_action in NEVER_PERMANENT_ACTIONS:
        raise ValueError(f"action '{clean_action}' cannot be permanently allowlisted")

    clean_match = _clean_match(match)
    if not clean_match:
        raise ValueError("match must include at least one supported field")
    if not (set(clean_match) & SCOPE_KEYS):
        raise ValueError("match must include a scoped path, repo, target, script_path, or tool_name field")

    rules = _load_rules()
    for rule in rules:
        if rule.get("action") == clean_action and rule.get("match") == clean_match:
            return rule

    rule = {
        "id": f"PAR-{uuid.uuid4().hex[:8].upper()}",
        "action": clean_action,
        "match": clean_match,
        "note": str(note or "").strip(),
        "source_approval_id": str(source_approval_id or "").strip() or None,
        "created_at": _now(),
    }
    rules.append(rule)
    _save_rules(rules)
    return rule


def delete_rule(rule_id: str) -> bool:
    rid = str(rule_id or "").strip()
    if not rid:
        return False
    rules = _load_rules()
    kept = [rule for rule in rules if rule.get("id") != rid]
    if len(kept) == len(rules):
        return False
    _save_rules(kept)
    return True


def find_matching_rule(action: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the first rule whose action and all match fields equal payload."""
    clean_action = _normalize_action(action)
    if not clean_action or clean_action in NEVER_PERMANENT_ACTIONS:
        return None
    incoming = _clean_match(payload)
    for rule in _load_rules():
        if rule.get("action") != clean_action:
            continue
        match = _clean_match(rule.get("match"))
        if match and all(incoming.get(key) == value for key, value in match.items()):
            return rule
    return None
