"""Scoped permanent approval rules for repeat low-risk approval requests."""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any

AI_LAB_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RULES_PATH = AI_LAB_ROOT / "memory" / "permanent_approval_rules.json"

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

# Keep this in sync with the frontend disabled actions.
NEVER_PERMANENT_ACTIONS = frozenset({"restart_service", "modify_registry"})


def _rules_path() -> Path:
    override = os.environ.get("AI_LAB_PERMANENT_ALLOWLIST_PATH", "").strip()
    return Path(override) if override else DEFAULT_RULES_PATH


def _normalize_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _normalize_match(match: dict[str, Any] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for key in MATCH_KEYS:
        value = _normalize_value((match or {}).get(key))
        if value:
            out[key] = value
    return out


def _read_rules() -> list[dict[str, Any]]:
    path = _rules_path()
    if not path.exists():
        return []
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _write_rules(rules: list[dict[str, Any]]) -> None:
    path = _rules_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, sort_keys=True)
        f.write("\n")
    tmp.replace(path)


def list_rules() -> list[dict[str, Any]]:
    """Return all configured permanent approval rules."""
    return list(_read_rules())


def approval_payload_subset(payload: dict[str, Any] | None) -> dict[str, str]:
    """Return only stable, non-empty fields that are safe to use for rule matching."""
    return _normalize_match(payload or {})


def brain_spec_match_payload(spec: dict[str, Any] | None) -> dict[str, str]:
    """Build a rule-match payload from approval queue rows and UI approval events."""
    row = dict(spec or {})
    payload = row.get("payload")
    if isinstance(payload, dict):
        row.update({k: v for k, v in payload.items() if k not in row})
    if row.get("action") and not row.get("action_type"):
        row["action_type"] = row.get("action")
    return approval_payload_subset(row)


def find_matching_rule(action: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the first rule whose action and scoped match fields all match exactly."""
    normalized_action = _normalize_value(action)
    candidate = approval_payload_subset(payload or {})
    if not normalized_action or not candidate:
        return None
    for rule in _read_rules():
        if _normalize_value(rule.get("action")) != normalized_action:
            continue
        match = _normalize_match(rule.get("match") if isinstance(rule.get("match"), dict) else {})
        if not match:
            continue
        if all(candidate.get(k) == v for k, v in match.items()):
            return rule
    return None


def add_rule(
    action: str,
    match: dict[str, Any] | None,
    *,
    note: str = "",
    source_approval_id: str | None = None,
) -> dict[str, Any]:
    """Persist a scoped permanent rule. Raises ValueError when the rule is unsafe."""
    normalized_action = _normalize_value(action)
    if not normalized_action:
        raise ValueError("action is required")
    if normalized_action in NEVER_PERMANENT_ACTIONS:
        raise ValueError(f"{normalized_action} cannot be permanently allowlisted")
    normalized_match = _normalize_match(match)
    if not normalized_match:
        raise ValueError("match must include at least one stable scoped field")

    rules = _read_rules()
    for rule in rules:
        if _normalize_value(rule.get("action")) == normalized_action and _normalize_match(
            rule.get("match") if isinstance(rule.get("match"), dict) else {}
        ) == normalized_match:
            return rule

    rule = {
        "id": f"PAR-{uuid.uuid4().hex[:8].upper()}",
        "action": normalized_action,
        "match": normalized_match,
        "note": _normalize_value(note),
        "source_approval_id": _normalize_value(source_approval_id),
    }
    rules.append(rule)
    _write_rules(rules)
    return rule


def delete_rule(rule_id: str) -> bool:
    rid = _normalize_value(rule_id)
    if not rid:
        return False
    rules = _read_rules()
    kept = [r for r in rules if _normalize_value(r.get("id")) != rid]
    if len(kept) == len(rules):
        return False
    _write_rules(kept)
    return True
