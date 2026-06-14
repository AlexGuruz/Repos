"""Persistent, scoped permanent approval rules.

Rules are intentionally conservative: a rule must match the action exactly and
must include at least one scope key such as a file path, repo, script, or tool.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parents[1]
_default_rules_path = _root / "memory" / "permanent_approval_rules.json"

NEVER_PERMANENT_ACTIONS = frozenset({"restart_service", "modify_registry"})

SCOPE_MATCH_KEYS = frozenset({
    "repo_id",
    "repo_path",
    "file_path",
    "path",
    "target",
    "script_path",
    "tool_name",
})

EXTRA_MATCH_KEYS = frozenset({"action_type", "reason", "detail"})
MATCH_KEYS = SCOPE_MATCH_KEYS | EXTRA_MATCH_KEYS


def _rules_path() -> Path:
    override = os.environ.get("AI_LAB_PERMANENT_ALLOWLIST_PATH", "").strip()
    return Path(override) if override else _default_rules_path


def _clean_action(action: Any) -> str:
    return str(action or "").strip()


def _clean_match(match: dict[str, Any] | None) -> dict[str, str]:
    cleaned: dict[str, str] = {}
    if not isinstance(match, dict):
        return cleaned
    for key, value in match.items():
        k = str(key or "").strip()
        if k not in MATCH_KEYS or value is None:
            continue
        v = str(value).strip()
        if v:
            cleaned[k] = v
    return cleaned


def _has_scope(match: dict[str, str]) -> bool:
    return any(k in SCOPE_MATCH_KEYS for k in match)


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
    rules: list[dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        action = _clean_action(item.get("action"))
        match = _clean_match(item.get("match"))
        if not action or not _has_scope(match):
            continue
        row = dict(item)
        row["action"] = action
        row["match"] = match
        rules.append(row)
    return rules


def _save_rules(rules: list[dict[str, Any]]) -> None:
    path = _rules_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def list_rules() -> list[dict[str, Any]]:
    """Return persisted permanent approval rules."""
    return _load_rules()


def add_rule(
    action: str,
    match: dict[str, Any] | None,
    *,
    note: str = "",
    source_approval_id: str | None = None,
) -> dict[str, Any]:
    """Persist a new scoped permanent approval rule."""
    clean_action = _clean_action(action)
    if not clean_action:
        raise ValueError("action is required.")
    if clean_action in NEVER_PERMANENT_ACTIONS:
        raise ValueError(f"action '{clean_action}' cannot be permanently allowlisted.")

    clean = _clean_match(match)
    if not _has_scope(clean):
        raise ValueError(
            "permanent approval rules require at least one scope key "
            "(file_path, path, target, repo_path, repo_id, script_path, or tool_name)."
        )

    rules = _load_rules()
    now = datetime.now(timezone.utc).isoformat()
    for existing in rules:
        if existing.get("action") == clean_action and existing.get("match") == clean:
            if note:
                existing["note"] = str(note).strip()
            if source_approval_id:
                existing["source_approval_id"] = str(source_approval_id).strip()
            existing["updated_at"] = now
            _save_rules(rules)
            return existing

    rule = {
        "id": f"PAR-{uuid.uuid4().hex[:8].upper()}",
        "action": clean_action,
        "match": clean,
        "note": str(note or "").strip(),
        "source_approval_id": str(source_approval_id or "").strip(),
        "created_at": now,
    }
    rules.append(rule)
    _save_rules(rules)
    return rule


def delete_rule(rule_id: str) -> bool:
    """Delete a permanent approval rule by id."""
    rid = str(rule_id or "").strip()
    if not rid:
        return False
    rules = _load_rules()
    kept = [rule for rule in rules if str(rule.get("id", "")).strip() != rid]
    if len(kept) == len(rules):
        return False
    _save_rules(kept)
    return True


def find_matching_rule(action: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return the first rule whose action and match subset exactly match payload."""
    clean_action = _clean_action(action)
    if not clean_action or clean_action in NEVER_PERMANENT_ACTIONS:
        return None
    clean_payload = _clean_match(payload)
    for rule in _load_rules():
        if rule.get("action") != clean_action:
            continue
        match = _clean_match(rule.get("match"))
        if not _has_scope(match):
            continue
        if all(clean_payload.get(key) == value for key, value in match.items()):
            return rule
    return None


def approval_payload_subset(payload: dict[str, Any] | None) -> dict[str, str]:
    """Extract the stable fields safe to show and use for permanent-rule matching."""
    return _clean_match(payload)


def brain_spec_match_payload(spec: dict[str, Any] | None) -> dict[str, str]:
    """Extract stable approval-queue fields for permanent-rule matching."""
    return _clean_match(spec)
