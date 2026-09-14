from __future__ import annotations

import os
import re
from typing import Any

from services.common.config_loader import load_config


def _extract_spreadsheet_id(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", text)
    if match:
        return match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", text):
        return text
    return ""


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
    """Resolve the rules-management Google spreadsheet ID from env or config."""
    for env_key in ("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID", "KYLO_RULES_MANAGEMENT_WORKBOOK_URL"):
        sid = _extract_spreadsheet_id(os.environ.get(env_key))
        if sid:
            return sid

    if cfg is None:
        try:
            cfg = load_config()
        except Exception:
            cfg = None

    sid = _extract_spreadsheet_id(_cfg_get(cfg, "rules.management_spreadsheet_id"))
    if sid:
        return sid
    return _extract_spreadsheet_id(_cfg_get(cfg, "rules.management_workbook_url"))


__all__ = ["get_rules_management_spreadsheet_id"]
