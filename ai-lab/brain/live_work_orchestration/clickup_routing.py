"""
Deterministic ClickUp list routing (Phase 10).

Maps normalized work categories to ClickUp list names. No API calls.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

# Canonical ClickUp list display names (exact strings for routing tests and UI).
CLICKUP_LIST_DEV_CORE = "Dev / Core Work"
CLICKUP_LIST_CLARIFICATIONS = "Agent Clarifications"
CLICKUP_LIST_AGENT_BILLS = "Agent Bills"
CLICKUP_LIST_AGENT_OPS = "Agent Ops"
CLICKUP_LIST_SYSTEM_FEEDBACK = "Agent System Feedback"
CLICKUP_LIST_COMPANY_FINANCES = "Company Finances"
CLICKUP_LIST_NUGZ_BILLS = "Nugz Bills"
CLICKUP_LIST_NUGZ_ORDERS = "Nugz Orders"

_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "agent_clarifications": (
        "clarify",
        "question",
        "missing info",
        "need answer",
        "unclear",
        "questions",
        "blockers",
        "blocker",
    ),
    "agent_bills": ("bill", "invoice", "payment", "due", "receipt", "expenses", "expense"),
    "agent_ops": ("ops", "runbook", "maintenance", "deploy", "incident", "system ops"),
    "agent_system_feedback": ("feedback", "bug", "issue", "ux", "friction", "improvements", "bugs"),
    "company_finances": ("finance", "budget", "cash", "p&l", "financial data", "financial"),
    "nugz_bills": ("nugz bill", "nugz invoice", "nugz payment", "vendor payments", "vendor payment"),
    "nugz_orders": ("nugz order", "fulfillment", "purchase order", "orders"),
    "dev_core_work": (
        "repo",
        "code",
        "pr",
        "feature",
        "refactor",
        "test",
        "dev",
        "repos",
        "ai work",
        "ai-work",
    ),
}

_CATEGORY_TO_CLICKUP_LIST: dict[str, str] = {
    "dev_core_work": CLICKUP_LIST_DEV_CORE,
    "agent_clarifications": CLICKUP_LIST_CLARIFICATIONS,
    "agent_bills": CLICKUP_LIST_AGENT_BILLS,
    "agent_ops": CLICKUP_LIST_AGENT_OPS,
    "agent_system_feedback": CLICKUP_LIST_SYSTEM_FEEDBACK,
    "company_finances": CLICKUP_LIST_COMPANY_FINANCES,
    "nugz_bills": CLICKUP_LIST_NUGZ_BILLS,
    "nugz_orders": CLICKUP_LIST_NUGZ_ORDERS,
    "other": CLICKUP_LIST_AGENT_OPS,
}

def _parse_scalar(text: str) -> str | None:
    v = text.strip()
    if v in ("null", "None", ""):
        return None
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    return v


def _load_clickup_mapping() -> dict[str, dict[str, str | None]]:
    """
    Minimal parser for config/clickup_mapping.yaml.
    Expected shape:
      <label>:
        list_name: "..."
        list_id: null
    """
    root = Path(__file__).resolve().parents[2]
    p = root / "config" / "clickup_mapping.yaml"
    out: dict[str, dict[str, str | None]] = {}
    if not p.is_file():
        return out
    current: str | None = None
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and line.endswith(":"):
            current = line[:-1].strip()
            out[current] = {}
            continue
        if current is None:
            continue
        s = line.strip()
        if ":" not in s:
            continue
        k, v = s.split(":", 1)
        key = k.strip()
        if key in ("list_name", "list_id"):
            out[current][key] = _parse_scalar(v)
    return out


_CLICKUP_MAPPING = _load_clickup_mapping()


def _resolve_clickup_target(list_label: str) -> dict[str, str]:
    cfg = _CLICKUP_MAPPING.get(list_label) or {}
    list_name = str(cfg.get("list_name") or list_label)
    list_id = cfg.get("list_id")
    target_list = str(list_id) if list_id else list_name
    return {"target_list": target_list, "target_list_name": list_name}


def classify_work_category(text: str) -> str:
    """Return canonical category key from free text (deterministic first-match order)."""
    t = (text or "").lower()
    for cat, keys in _CATEGORY_KEYWORDS.items():
        if any(k in t for k in keys):
            return cat
    return "other"


def map_category_to_clickup_list(category: str) -> str:
    """Map a category key to the exact ClickUp list name."""
    return _CATEGORY_TO_CLICKUP_LIST.get(category, CLICKUP_LIST_AGENT_OPS)


def _text_from_item(item: dict[str, Any] | str, keys: tuple[str, ...]) -> str:
    if isinstance(item, str):
        return item
    return " ".join(str(item.get(k) or "") for k in keys)


def route_task(item: dict[str, Any] | str) -> dict[str, Any]:
    """Route a work item to a ClickUp list for task-shaped work."""
    text = _text_from_item(item, ("title", "notes", "reason", "category", "message"))
    cat = classify_work_category(text)
    mapped = map_category_to_clickup_list(cat)
    return {"category": cat, **_resolve_clickup_target(mapped)}


def route_comment(item: dict[str, Any] | str) -> dict[str, Any]:
    """Route a comment-shaped payload to a ClickUp list (same taxonomy as tasks)."""
    text = _text_from_item(item, ("message", "body", "notes", "reason", "category", "title"))
    cat = classify_work_category(text)
    mapped = map_category_to_clickup_list(cat)
    return {"category": cat, **_resolve_clickup_target(mapped)}
