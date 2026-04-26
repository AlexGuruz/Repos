"""
Durable rules: skip the approval card when action + payload keys match.
Stored at ai-lab/state/permanent_approvals.json (created on first use).
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_STATE_PATH = _ROOT / "state" / "permanent_approvals.json"

# Never auto-approve or store as permanent via API (override only by editing JSON locally).
NEVER_PERMANENT_ACTIONS = frozenset({"restart_service", "modify_registry"})

# Keys forwarded on approval events and used for rule matching / UI.
MATCH_PAYLOAD_KEYS = frozenset(
    {
        "repo_id",
        "repo_path",
        "file_path",
        "path",
        "target",
        "script_path",
        "detail",
        "tool_name",
        "action_type",
        "reason",
    }
)


def _state_path() -> Path:
    return _STATE_PATH


def _load() -> dict[str, Any]:
    p = _state_path()
    if not p.is_file():
        return {"version": 1, "rules": []}
    try:
        with p.open(encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get("rules"), list):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"version": 1, "rules": []}


def _save(data: dict[str, Any]) -> None:
    p = _state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def list_rules() -> list[dict[str, Any]]:
    return list(_load().get("rules", []))


def approval_payload_subset(payload: dict[str, Any] | None) -> dict[str, Any]:
    """JSON-safe subset for WS / persistence (limits detail size)."""
    if not payload:
        return {}
    out: dict[str, Any] = {}
    for k in MATCH_PAYLOAD_KEYS:
        if k not in payload:
            continue
        v = payload[k]
        if v is None:
            continue
        if isinstance(v, (str, int, float, bool)):
            s = str(v) if not isinstance(v, str) else v
            if k == "detail" and len(s) > 500:
                s = s[:500]
            out[k] = s
        elif isinstance(v, dict) and k == "args":
            out[k] = v
    return out


def _norm(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _payload_matches(rule_match: dict[str, Any], payload: dict[str, Any]) -> bool:
    for k, want in rule_match.items():
        w = _norm(want)
        if not w:
            continue
        if _norm(payload.get(k)) != w:
            return False
    return True


def find_matching_rule(action: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    action = (action or "").strip()
    if not action or action in NEVER_PERMANENT_ACTIONS:
        return None
    payload = payload or {}
    for r in _load().get("rules", []):
        if not isinstance(r, dict):
            continue
        if (r.get("action") or "").strip() != action:
            continue
        m = r.get("match") or {}
        if not isinstance(m, dict) or not m:
            continue
        if _payload_matches(m, payload):
            return r
    return None


def add_rule(
    action: str,
    match: dict[str, Any],
    *,
    note: str = "",
    source_approval_id: str | None = None,
) -> dict[str, Any]:
    action = (action or "").strip()
    if not action:
        raise ValueError("action is required")
    if action in NEVER_PERMANENT_ACTIONS:
        raise ValueError(f"action '{action}' cannot be added to permanent allowlist")
    if not isinstance(match, dict):
        raise ValueError("match must be an object")

    rid = f"PAR-{uuid.uuid4().hex[:8].upper()}"
    clean_match: dict[str, Any] = {}
    for k, raw in match.items():
        if isinstance(raw, dict):
            clean_match[k] = raw
            continue
        s = _norm(raw)
        if s:
            clean_match[k] = s
    if not clean_match:
        raise ValueError("match must contain at least one non-empty value")
    rule = {
        "id": rid,
        "action": action,
        "match": clean_match,
        "note": (note or "").strip()[:500],
        "source_approval_id": (source_approval_id or "").strip() or None,
    }
    data = _load()
    rules = data.setdefault("rules", [])
    rules.append(rule)
    _save(data)
    return rule


def delete_rule(rule_id: str) -> bool:
    rid = (rule_id or "").strip()
    if not rid:
        return False
    data = _load()
    rules = data.get("rules", [])
    new_rules = [r for r in rules if isinstance(r, dict) and r.get("id") != rid]
    if len(new_rules) == len(rules):
        return False
    data["rules"] = new_rules
    _save(data)
    return True


def brain_spec_match_payload(spec: dict[str, Any]) -> dict[str, Any]:
    """Map approval queue row to match payload (same keys as rules)."""
    return approval_payload_subset(
        {
            "file_path": spec.get("file_path"),
            "action_type": spec.get("action_type") or spec.get("action"),
            "tool_name": spec.get("tool_name"),
            "reason": spec.get("reason"),
        }
    )
