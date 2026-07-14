from __future__ import annotations

import os
from typing import Any

from services.sheets.poster import _extract_spreadsheet_id


def _cfg_get(cfg: Any, key: str) -> Any:
    if cfg is None:
        return None
    get = getattr(cfg, "get", None)
    if callable(get):
        return get(key)
    cur = cfg
    for part in key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


def get_rules_management_spreadsheet_id(cfg: Any = None) -> str:
    spreadsheet_id = str(
        _cfg_get(cfg, "rules.management_spreadsheet_id")
        or os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID")
        or ""
    ).strip()
    if spreadsheet_id:
        return spreadsheet_id

    url = str(_cfg_get(cfg, "rules.management_workbook_url") or "").strip()
    if not url:
        return ""
    return _extract_spreadsheet_id(url)


__all__ = ["get_rules_management_spreadsheet_id"]
