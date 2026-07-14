from __future__ import annotations

import os
import re
from typing import Any


_SPREADSHEET_URL_RE = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]+)")


def _cfg_get(cfg: Any, dotted_key: str, default: Any = None) -> Any:
    if cfg is None:
        return default
    getter = getattr(cfg, "get", None)
    if callable(getter):
        value = getter(dotted_key, None)
        if value not in (None, ""):
            return value
    cur: Any = cfg
    for part in dotted_key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur if cur not in (None, "") else default


def spreadsheet_id_from_url(value: str | None) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    match = _SPREADSHEET_URL_RE.search(text)
    if match:
        return match.group(1)
    if "/" not in text and " " not in text:
        return text
    return None


def get_rules_management_spreadsheet_id(cfg: Any = None) -> str | None:
    env_value = os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID")
    if env_value:
        return spreadsheet_id_from_url(env_value)

    configured_id = _cfg_get(cfg, "rules.management_spreadsheet_id")
    if configured_id:
        return spreadsheet_id_from_url(str(configured_id))

    configured_url = _cfg_get(cfg, "rules.management_workbook_url")
    return spreadsheet_id_from_url(str(configured_url)) if configured_url else None


__all__ = ["get_rules_management_spreadsheet_id", "spreadsheet_id_from_url"]
