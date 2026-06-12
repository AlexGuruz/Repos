"""Persistent, scoped permanent approval rules for the brain/command-center.

Rules are intentionally narrow: an action only matches when every stored match
field is present with the same normalized value in the candidate payload.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parents[1]

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

# Keep this in sync with the frontend's disabled "Always allow" actions.
NEVER_PERMANENT_ACTIONS = frozenset({"restart_service", "modify_registry"})


def _rules_path() -> Path:
    override = (os.environ.get("AI_LAB_PERMANENT_ALLOWLIST_PATH") or "").strip()
    if override:
        return Path(override)
    return _root / "logs" / "approval_logs" / "permanent_allowlist.json"


def _normalize_action(action: Any) -> str:
    return str(action or "").strip()


def _normalize_value(value: Any) -> str:
    return str(value).strip()


def approval_payload_subset(payload: dict[str, Any] | None) -> dict[str, str]:
    """Return the stable subset of approval/tool payload fields used for matching."""
    if not isinstance(payload, dict):
        return {}
    out: dict[str, str] = {}
    for key in PAYLOAD_MATCH_KEYS:
        value = payload.get(key)
        if value is None:
            continue
        normalized = _normalize_value(value)
        if normalized:
            out[key] = normalized
    return out


def brain_spec_match_payload(spec: Any) -> dict[str, str]:
    """Build a match payload from an ApprovalSpec dataclass or queue row dict."""
    if spec is None:
        return {}
    if isinstance(spec, dict):
        return approval_payload_subset(spec)
    raw: dict[str, Any] = {}
    for key in PAYLOAD_MATCH_KEYS:
        if hasattr(spec, key):
            raw[key] = getattr(spec, key)
    return approval_payload_subset(raw)


def _load_rules() -> list[dict[str, Any]]:
    path = _rules_path()
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def _save_rules(rules: list[dict[str, Any]]) -> None:
    path = _rules_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, sort_keys=True)
        f.write("\n")
    tmp.replace(path)


def _rule_matches(rule: dict[str, Any], action: str, payload: dict[str, str]) -> bool:
    if _normalize_action(rule.get("action")) != action:
        return False
    match = rule.get("match")
    if not isinstance(match, dict) or not match:
        return False
    candidate = approval_payload_subset(payload)
    for key, wanted in match.items():
        wanted_s = _normalize_value(wanted)
        if not wanted_s or candidate.get(str(key)) != wanted_s:
            return False
    return True


def list_rules() -> list[dict[str, Any]]:
    """Return all stored permanent approval rules."""
    return _load_rules()


def add_rule(
    action: str,
    match: dict[str, Any] | None,
    *,
    note: str = "",
    source_approval_id: str | None = None,
) -> dict[str, Any]:
    """Persist a scoped permanent approval rule and return it."""
    action_s = _normalize_action(action)
    if not action_s:
        raise ValueError("action is required")
    if action_s in NEVER_PERMANENT_ACTIONS:
        raise ValueError(f"action cannot be permanently allowlisted: {action_s}")
    match_s = approval_payload_subset(match or {})
    if not match_s:
        raise ValueError("match must include at least one stable payload field")

    rules = _load_rules()
    for rule in rules:
        if _normalize_action(rule.get("action")) == action_s and approval_payload_subset(rule.get("match")) == match_s:
            return rule

    rule = {
        "id": f"perm-{uuid.uuid4().hex[:12]}",
        "action": action_s,
        "match": match_s,
        "note": str(note or "").strip(),
        "source_approval_id": str(source_approval_id or "").strip() or None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    rules.append(rule)
    _save_rules(rules)
    return rule


def delete_rule(rule_id: str) -> bool:
    """Delete a permanent rule by id."""
    rid = str(rule_id or "").strip()
    if not rid:
        return False
    rules = _load_rules()
    kept = [rule for rule in rules if str(rule.get("id") or "") != rid]
    if len(kept) == len(rules):
        return False
    _save_rules(kept)
    return True


def find_matching_rule(action: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the first rule that exactly scopes the action/payload pair."""
    action_s = _normalize_action(action)
    if not action_s or action_s in NEVER_PERMANENT_ACTIONS:
        return None
    candidate = approval_payload_subset(payload or {})
    if not candidate:
        return None
    for rule in _load_rules():
        if _rule_matches(rule, action_s, candidate):
            return rule
    return None
