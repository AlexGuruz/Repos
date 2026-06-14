"""Persistent permanent approval rules for approval-gated actions."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parents[1]
_rules_path = _root / "logs" / "approval_logs" / "permanent_allowlist.json"

_MATCH_KEYS = (
    "file_path",
    "path",
    "target",
    "repo_path",
    "script_path",
    "repo_id",
    "service",
    "service_name",
    "tool_name",
    "command",
    "config_path",
    "sheet_id",
    "range",
)
_PATH_KEYS = ("file_path", "path", "target", "repo_path", "script_path")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_action(action: str) -> str:
    return str(action or "").strip()


def _clean_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        return v or None
    if isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, (list, tuple, dict)):
        return value if value else None
    return str(value).strip() or None


def _value_key(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return json.dumps(value, sort_keys=True, default=str)


def _clean_match(match: dict[str, Any] | None, *, restrict_keys: bool) -> dict[str, Any]:
    if not isinstance(match, dict):
        return {}
    keys = _MATCH_KEYS if restrict_keys else tuple(match.keys())
    out: dict[str, Any] = {}
    for key in keys:
        if key not in match:
            continue
        value = _clean_value(match.get(key))
        if value is not None:
            out[str(key)] = value

    # Canonicalize path-like payloads so rules created from either chat approvals
    # or supervisor payloads can match later invocations with different key names.
    if "file_path" not in out:
        for key in _PATH_KEYS:
            if key in out:
                out["file_path"] = out[key]
                break
    return out


def _load_rules() -> list[dict[str, Any]]:
    if not _rules_path.exists():
        return []
    try:
        with _rules_path.open(encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    return [row for row in data if isinstance(row, dict)]


def _save_rules(rules: list[dict[str, Any]]) -> None:
    _rules_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = _rules_path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2, sort_keys=True)
        f.write("\n")
    tmp.replace(_rules_path)


def approval_payload_subset(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Return stable fields safe to use for permanent-rule matching."""
    return _clean_match(payload, restrict_keys=True)


def brain_spec_match_payload(spec: dict[str, Any] | None) -> dict[str, Any]:
    """Extract stable match fields from a queued approval spec."""
    if not isinstance(spec, dict):
        return {}
    out = approval_payload_subset(spec)
    payload = spec.get("payload")
    if isinstance(payload, dict):
        out.update(approval_payload_subset(payload))
    return out


def list_rules() -> list[dict[str, Any]]:
    return _load_rules()


def add_rule(
    action: str,
    match: dict[str, Any] | None,
    *,
    note: str = "",
    source_approval_id: str | None = None,
) -> dict[str, Any]:
    action_name = _norm_action(action)
    if not action_name:
        raise ValueError("action is required")
    match_payload = _clean_match(match, restrict_keys=False)
    if not match_payload:
        raise ValueError("match must include at least one stable field")

    rule = {
        "id": f"perm-{uuid.uuid4().hex[:8].upper()}",
        "action": action_name,
        "match": match_payload,
        "note": str(note or "").strip(),
        "source_approval_id": str(source_approval_id or "").strip() or None,
        "created_at": _now(),
    }
    rules = _load_rules()
    rules.append(rule)
    _save_rules(rules)
    return rule


def delete_rule(rule_id: str) -> bool:
    rid = str(rule_id or "").strip()
    if not rid:
        return False
    rules = _load_rules()
    kept = [row for row in rules if str(row.get("id") or "") != rid]
    if len(kept) == len(rules):
        return False
    _save_rules(kept)
    return True


def find_matching_rule(action: str, payload: dict[str, Any] | None) -> dict[str, Any] | None:
    action_name = _norm_action(action)
    if not action_name:
        return None
    candidate = _clean_match(payload, restrict_keys=False)
    if not candidate:
        return None

    for rule in _load_rules():
        if _norm_action(str(rule.get("action") or "")) != action_name:
            continue
        match = _clean_match(rule.get("match"), restrict_keys=False)
        if not match:
            continue
        if all(key in candidate and _value_key(candidate[key]) == _value_key(value) for key, value in match.items()):
            return rule
    return None
