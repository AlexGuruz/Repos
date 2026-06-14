"""
Persistent permanent approval rules.

Rules are deliberately exact-match and scoped: a permanent approval may only
skip a future approval when the action matches and every stored match key has
the same value in the new approval payload.
"""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parents[1]
_DEFAULT_RULES_PATH = _root / "logs" / "approval_logs" / "permanent_allowlist.json"

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

_SCOPING_KEYS = frozenset({
    "repo_id",
    "repo_path",
    "file_path",
    "path",
    "target",
    "script_path",
    "tool_name",
})


def _rules_path() -> Path:
    override = (os.environ.get("AI_LAB_PERMANENT_ALLOWLIST_PATH") or "").strip()
    return Path(override).expanduser() if override else _DEFAULT_RULES_PATH


def _string_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
    elif isinstance(value, (int, float, bool)):
        s = str(value).strip()
    else:
        return None
    return s or None


def _clean_action(action: Any) -> str:
    return str(action or "").strip()


def approval_payload_subset(payload: dict[str, Any] | None) -> dict[str, str]:
    """Return stable, string-only fields that are safe to use for matching."""
    source = payload or {}
    subset: dict[str, str] = {}
    for key in PAYLOAD_MATCH_KEYS:
        value = _string_value(source.get(key))
        if value:
            subset[key] = value
    return subset


def brain_spec_match_payload(spec: dict[str, Any] | None) -> dict[str, str]:
    """Normalize a brain approval queue row into a permanent-rule payload."""
    source = dict(spec or {})
    if "action_type" not in source and source.get("action"):
        source["action_type"] = source.get("action")
    if "detail" not in source and source.get("reason"):
        source["detail"] = source.get("reason")
    return approval_payload_subset(source)


def _load_rules() -> list[dict[str, Any]]:
    path = _rules_path()
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    rows = data.get("rules") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        return []
    rules: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        action = _clean_action(row.get("action"))
        match = approval_payload_subset(row.get("match") if isinstance(row.get("match"), dict) else {})
        if not action or not match:
            continue
        clean = dict(row)
        clean["action"] = action
        clean["match"] = match
        rules.append(clean)
    return rules


def _save_rules(rules: list[dict[str, Any]]) -> None:
    path = _rules_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"rules": rules}, f, indent=2)
            f.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def list_rules() -> list[dict[str, Any]]:
    return [dict(rule) for rule in _load_rules()]


def _validate_rule(action: str, match: dict[str, str]) -> None:
    if not action:
        raise ValueError("action is required.")
    if action in NEVER_PERMANENT_ACTIONS:
        raise ValueError(f"action '{action}' cannot be made permanent.")
    if not match:
        raise ValueError("match must include at least one scoped field.")
    if not (_SCOPING_KEYS & set(match)):
        raise ValueError("match must include a scoped field such as file_path, script_path, repo_path, target, or tool_name.")


def add_rule(
    action: str,
    match: dict[str, Any] | None,
    *,
    note: str = "",
    source_approval_id: str | None = None,
) -> dict[str, Any]:
    clean_action = _clean_action(action)
    clean_match = approval_payload_subset(match or {})
    _validate_rule(clean_action, clean_match)

    rules = _load_rules()
    for rule in rules:
        if rule.get("action") == clean_action and rule.get("match") == clean_match:
            return dict(rule)

    rule = {
        "id": f"PAR-{uuid.uuid4().hex[:8].upper()}",
        "action": clean_action,
        "match": clean_match,
        "note": str(note or "").strip(),
        "source_approval_id": str(source_approval_id or "").strip(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    rules.append(rule)
    _save_rules(rules)
    return dict(rule)


def delete_rule(rule_id: str) -> bool:
    rid = str(rule_id or "").strip()
    if not rid:
        return False
    rules = _load_rules()
    remaining = [rule for rule in rules if str(rule.get("id") or "") != rid]
    if len(remaining) == len(rules):
        return False
    _save_rules(remaining)
    return True


def find_matching_rule(action: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    clean_action = _clean_action(action)
    if not clean_action or clean_action in NEVER_PERMANENT_ACTIONS:
        return None
    candidate = approval_payload_subset(payload or {})
    for rule in _load_rules():
        if rule.get("action") != clean_action:
            continue
        match = rule.get("match")
        if not isinstance(match, dict):
            continue
        if all(candidate.get(key) == value for key, value in match.items()):
            return dict(rule)
    return None
