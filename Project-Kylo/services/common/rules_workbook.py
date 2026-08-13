from __future__ import annotations

import os
import re
from typing import Any


_SHEET_ID_RE = re.compile(r"/spreadsheets/d/([^/?#]+)")


def extract_spreadsheet_id(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = _SHEET_ID_RE.search(text)
    if match:
        return match.group(1).strip()
    if "/" not in text and " " not in text:
        return text
    return ""


def _cfg_get(cfg: Any, dotted_key: str) -> Any:
    if cfg is None:
        return None
    getter = getattr(cfg, "get", None)
    if callable(getter):
        value = getter(dotted_key)
        if value is not None:
            return value
    cur = cfg
    if hasattr(cur, "data"):
        cur = getattr(cur, "data")
    for part in dotted_key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def _load_config_best_effort() -> Any:
    try:
        from services.common.config_loader import load_config

        return load_config()
    except Exception:
        return None


def get_rules_management_spreadsheet_id(cfg: Any | None = None) -> str:
    """Resolve the rules-management workbook id from env or Kylo config."""
    env_id = extract_spreadsheet_id(os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID"))
    if env_id:
        return env_id

    active_cfg = cfg if cfg is not None else _load_config_best_effort()

    configured_id = extract_spreadsheet_id(_cfg_get(active_cfg, "rules.management_spreadsheet_id"))
    if configured_id:
        return configured_id

    return extract_spreadsheet_id(_cfg_get(active_cfg, "rules.management_workbook_url"))


__all__ = ["extract_spreadsheet_id", "get_rules_management_spreadsheet_id"]
