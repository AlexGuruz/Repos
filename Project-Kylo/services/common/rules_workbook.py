from __future__ import annotations

import os
from typing import Any


def _extract_spreadsheet_id(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    for marker in ("/spreadsheets/d/", "/d/"):
        if marker in text:
            try:
                return text.split(marker, 1)[1].split("/", 1)[0].strip()
            except Exception:
                return text
    return text


def _cfg_get(cfg: Any | None, dotted_key: str) -> Any:
    if cfg is None:
        return None
    if isinstance(cfg, dict):
        cur: Any = cfg
        for part in dotted_key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur
    getter = getattr(cfg, "get", None)
    if callable(getter):
        try:
            return getter(dotted_key)
        except Exception:
            return None
    return None


def get_rules_management_spreadsheet_id(cfg: Any | None = None) -> str:
    """Resolve the rules-management workbook from env or layered config."""
    for env_key in ("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "KYLO_RULES_MANAGEMENT_WORKBOOK_URL"):
        sid = _extract_spreadsheet_id(os.environ.get(env_key))
        if sid:
            return sid

    sid = _extract_spreadsheet_id(_cfg_get(cfg, "rules.management_spreadsheet_id"))
    if sid:
        return sid
    return _extract_spreadsheet_id(_cfg_get(cfg, "rules.management_workbook_url"))
