from __future__ import annotations

import os
from typing import Any


def _cfg_get(cfg: Any, dotted: str, default: Any = None) -> Any:
    if cfg is None:
        return default
    if hasattr(cfg, "get"):
        try:
            value = cfg.get(dotted, default)
        except TypeError:
            value = default
        if value is not None:
            return value
    cur = getattr(cfg, "data", None)
    if not isinstance(cur, dict) and isinstance(cfg, dict):
        cur = cfg
    if not isinstance(cur, dict):
        return default
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _extract_spreadsheet_id(value: str) -> str:
    text = str(value or "").strip()
    if "/spreadsheets/d/" in text:
        try:
            return text.split("/spreadsheets/d/", 1)[1].split("/", 1)[0].split("?", 1)[0]
        except Exception:
            return text
    return text


def get_rules_management_spreadsheet_id(cfg: Any = None) -> str:
    """Resolve the rules-management workbook spreadsheet ID from env or config."""
    explicit = (os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID") or "").strip()
    if explicit:
        return _extract_spreadsheet_id(explicit)

    cfg_id = str(_cfg_get(cfg, "rules.management_spreadsheet_id", "") or "").strip()
    if cfg_id:
        return _extract_spreadsheet_id(cfg_id)

    env_url = (os.environ.get("KYLO_RULES_MANAGEMENT_WORKBOOK_URL") or "").strip()
    cfg_url = str(_cfg_get(cfg, "rules.management_workbook_url", "") or "").strip()
    return _extract_spreadsheet_id(env_url or cfg_url)


__all__ = ["get_rules_management_spreadsheet_id"]
