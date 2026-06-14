"""
Scoped permanent approval rules.

Rules are action-specific and only match when every saved payload field has
the same value on a future approval request. Empty or action-only rules are
rejected so a permanent approval cannot become a blanket bypass.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_RULES_PATH = _ROOT / "memory" / "permanent_allowlist.json"

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


def _rules_path() -> Path:
    override = os.environ.get("AI_LAB_PERMANENT_ALLOWLIST_PATH", "").strip()
    return Path(override) if override else _DEFAULT_RULES_PATH


def _normalize_action(action: str | None) -> str:
    return (action or "").strip().lower()


def _clean_scalar(value: Any) -> str | None:
    if value is None or isinstance(value, (dict, list, tuple, set)):
        return None
    text = str(value).strip()
    return text or None


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
    return [r for r in data if isinstance(r, dict)]


def _save_rules(rules: list[dict[str, Any]]) -> None:
    path = _rules_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)
        f.write("\n")
    tmp.replace(path)


def approval_payload_subset(payload: dict[str, Any] | None) -> dict[str, str]:
    """Return the stable scalar payload fields allowed for permanent matching."""
    source = dict(payload or {})
    args = source.get("args")
    if isinstance(args, dict):
        for key, value in args.items():
            source.setdefault(key, value)

    out: dict[str, str] = {}
    for key in PAYLOAD_MATCH_KEYS:
        value = _clean_scalar(source.get(key))
        if value is not None:
            out[key] = value
    return out


def brain_spec_match_payload(spec: dict[str, Any] | None) -> dict[str, str]:
    """Build a matching payload from a brain approval queue row or proposal spec."""
    return approval_payload_subset(spec)


def list_rules() -> list[dict[str, Any]]:
    return _load_rules()


def add_rule(
    action: str,
    match: dict[str, Any] | None,
    *,
    note: str = "",
    source_approval_id: str | None = None,
) -> dict[str, Any]:
    action_key = _normalize_action(action)
    if not action_key:
        raise ValueError("action is required")
    if action_key in NEVER_PERMANENT_ACTIONS:
        raise ValueError(f"{action_key} cannot be permanently allowlisted")

    match_subset = approval_payload_subset(match)
    if not match_subset:
        raise ValueError("match must include at least one scoped payload field")

    rules = _load_rules()
    now = datetime.now(timezone.utc).isoformat()
    rule = {
        "id": f"PAR-{uuid.uuid4().hex[:8].upper()}",
        "action": action_key,
        "match": match_subset,
        "note": (note or "").strip(),
        "source_approval_id": (source_approval_id or "").strip() or None,
        "created_at": now,
    }
    rules.append(rule)
    _save_rules(rules)
    return rule


def delete_rule(rule_id: str) -> bool:
    rid = (rule_id or "").strip()
    if not rid:
        return False
    rules = _load_rules()
    kept = [r for r in rules if str(r.get("id") or "") != rid]
    if len(kept) == len(rules):
        return False
    _save_rules(kept)
    return True


def find_matching_rule(action: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    action_key = _normalize_action(action)
    if not action_key or action_key in NEVER_PERMANENT_ACTIONS:
        return None
    probe = approval_payload_subset(payload)
    if not probe:
        return None

    for rule in _load_rules():
        if _normalize_action(str(rule.get("action") or "")) != action_key:
            continue
        match = rule.get("match")
        if not isinstance(match, dict) or not match:
            continue
        normalized_match = approval_payload_subset(match)
        if normalized_match and all(probe.get(k) == v for k, v in normalized_match.items()):
            return rule
    return None
