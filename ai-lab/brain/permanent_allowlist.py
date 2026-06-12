"""Persistent, scoped permanent approval rules for the AI Lab brain.

Rules are intentionally simple: an action must match exactly and every stored
match key must equal the candidate payload value. Empty or unscoped rules are
rejected so a permanent approval cannot become a blanket bypass.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

_ROOT = Path(__file__).resolve().parents[1]
_RULES_PATH = _ROOT / "memory" / "permanent_allowlist.json"

NEVER_PERMANENT_ACTIONS = frozenset({"restart_service", "modify_registry"})

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


def _as_mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    return {
        key: getattr(value, key)
        for key in MATCH_KEYS
        if hasattr(value, key)
    }


def _clean_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_match(payload: Mapping[str, Any] | None) -> dict[str, str]:
    raw = _as_mapping(payload)
    out: dict[str, str] = {}

    for nested_key in ("payload", "supervisor_payload", "args"):
        nested = raw.get(nested_key)
        if isinstance(nested, Mapping):
            out.update(_normalize_match(nested))

    for key in MATCH_KEYS:
        value = _clean_value(raw.get(key))
        if value is not None:
            out[key] = value
    return out


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
    return [dict(rule) for rule in data if isinstance(rule, Mapping)]


def _save_rules(rules: list[dict[str, Any]]) -> None:
    _RULES_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _RULES_PATH.with_suffix(_RULES_PATH.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, sort_keys=True)
        f.write("\n")
    tmp.replace(_RULES_PATH)


def brain_spec_match_payload(spec_or_dict: Any) -> dict[str, str]:
    """Return the safe subset of an approval/spec payload used for matching."""
    return _normalize_match(_as_mapping(spec_or_dict))


def approval_payload_subset(payload: Mapping[str, Any] | None) -> dict[str, str]:
    """Return the safe subset of a supervisor invoke payload used for matching."""
    return _normalize_match(payload)


def list_rules() -> list[dict[str, Any]]:
    return _load_rules()


def add_rule(
    action: str,
    match: Mapping[str, Any] | None,
    *,
    note: str = "",
    source_approval_id: str | None = None,
) -> dict[str, Any]:
    action_name = (action or "").strip()
    if not action_name:
        raise ValueError("action is required")
    if action_name in NEVER_PERMANENT_ACTIONS:
        raise ValueError(f"Action '{action_name}' cannot be permanently allowlisted.")

    scoped_match = _normalize_match(match)
    if not scoped_match:
        raise ValueError("match must include at least one scoped payload field")

    rule = {
        "id": f"PAR-{uuid.uuid4().hex[:8].upper()}",
        "action": action_name,
        "match": scoped_match,
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
    kept = [rule for rule in rules if str(rule.get("id") or "") != rid]
    if len(kept) == len(rules):
        return False
    _save_rules(kept)
    return True


def find_matching_rule(action: str, match_payload: Mapping[str, Any] | None) -> dict[str, Any] | None:
    action_name = (action or "").strip()
    if not action_name or action_name in NEVER_PERMANENT_ACTIONS:
        return None

    candidate = _normalize_match(match_payload)
    if not candidate:
        return None

    for rule in _load_rules():
        if str(rule.get("action") or "").strip() != action_name:
            continue
        rule_match = _normalize_match(rule.get("match") if isinstance(rule.get("match"), Mapping) else {})
        if not rule_match:
            continue
        if all(candidate.get(key) == value for key, value in rule_match.items()):
            return rule
    return None
