"""Permanent approval rules for narrowly scoped, repeated actions.

Rules are intentionally conservative: an action must match exactly and every
stored match key must equal the incoming payload value. Missing values do not
match, which keeps "always allow similar" from becoming a broad bypass.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_AI_LAB_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_RULES_PATH = _AI_LAB_ROOT / "logs" / "approval_logs" / "permanent_allowlist.json"
_RULES_PATH_ENV = "AI_LAB_PERMANENT_ALLOWLIST_PATH"

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


def _rules_path() -> Path:
    override = os.environ.get(_RULES_PATH_ENV, "").strip()
    return Path(override) if override else _DEFAULT_RULES_PATH


def _normalize_value(value: Any) -> str | None:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return None
    text = str(value).strip()
    return text or None


def _normalize_match(raw: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key in MATCH_KEYS:
        value = _normalize_value(raw.get(key))
        if value is not None:
            out[key] = value
    return out


def approval_payload_subset(payload: dict[str, Any] | None) -> dict[str, str]:
    """Return the stable, scalar payload fields allowed for rule matching."""
    return _normalize_match(payload)


def brain_spec_match_payload(spec: dict[str, Any] | None) -> dict[str, str]:
    """Build a rule-match payload from a brain approval queue row."""
    return approval_payload_subset(spec)


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
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)
        f.write("\n")
    tmp.replace(path)


def list_rules() -> list[dict[str, Any]]:
    return _load_rules()


def add_rule(
    action: str,
    match: dict[str, Any] | None,
    *,
    note: str = "",
    source_approval_id: str | None = None,
) -> dict[str, Any]:
    action_name = (action or "").strip()
    if not action_name:
        raise ValueError("action is required")
    if action_name in NEVER_PERMANENT_ACTIONS:
        raise ValueError(f"action '{action_name}' cannot be permanently allowlisted")
    normalized_match = _normalize_match(match)
    if not normalized_match:
        raise ValueError("match must include at least one scoped field")

    rule = {
        "id": f"PERM-{uuid.uuid4().hex[:8].upper()}",
        "action": action_name,
        "match": normalized_match,
        "note": (note or "").strip(),
        "source_approval_id": (source_approval_id or "").strip() or None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    rules = _load_rules()
    rules.append(rule)
    _save_rules(rules)
    return rule


def delete_rule(rule_id: str) -> bool:
    rid = (rule_id or "").strip()
    if not rid:
        return False
    rules = _load_rules()
    kept = [row for row in rules if str(row.get("id") or "") != rid]
    if len(kept) == len(rules):
        return False
    _save_rules(kept)
    return True


def find_matching_rule(action: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    action_name = (action or "").strip()
    if not action_name or action_name in NEVER_PERMANENT_ACTIONS:
        return None
    normalized_payload = _normalize_match(payload)
    for rule in _load_rules():
        if str(rule.get("action") or "").strip() != action_name:
            continue
        rule_match = _normalize_match(rule.get("match") if isinstance(rule.get("match"), dict) else {})
        if rule_match and all(normalized_payload.get(key) == value for key, value in rule_match.items()):
            return rule
    return None
