from __future__ import annotations

import os
from typing import Any


def _cfg_get(cfg: Any, key: str, default: Any = None) -> Any:
    if cfg is None:
        return default
    if isinstance(cfg, dict):
        cur: Any = cfg
        for part in key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur
    getter = getattr(cfg, "get", None)
    if callable(getter):
        return getter(key, default)
    return default


def _extract_spreadsheet_id(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    marker = "/spreadsheets/d/"
    if marker in text:
        try:
            return text.split(marker, 1)[1].split("/", 1)[0].strip() or None
        except Exception:
            return text
    return text


def get_rules_management_spreadsheet_id(cfg: Any = None) -> str | None:
    """Resolve the rules-management workbook ID without touching Google APIs."""
    env_id = _extract_spreadsheet_id(os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID"))
    if env_id:
        return env_id

    if cfg is None:
        try:
            from services.common.config_loader import load_config

            cfg = load_config()
        except Exception:
            cfg = None

    configured_id = _extract_spreadsheet_id(_cfg_get(cfg, "rules.management_spreadsheet_id"))
    if configured_id:
        return configured_id

    env_url = _extract_spreadsheet_id(os.environ.get("KYLO_RULES_MANAGEMENT_WORKBOOK_URL"))
    if env_url:
        return env_url

    return _extract_spreadsheet_id(_cfg_get(cfg, "rules.management_workbook_url"))
