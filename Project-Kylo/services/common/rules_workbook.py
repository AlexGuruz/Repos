from __future__ import annotations

import os
import re
from typing import Any


_SPREADSHEET_ID_RE = re.compile(r"/spreadsheets/d/([^/#?]+)")


def _cfg_get(cfg: Any, dotted_key: str) -> Any:
    if cfg is None:
        return None
    if isinstance(cfg, dict):
        cur = cfg
        for part in dotted_key.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return None
        return cur
    getter = getattr(cfg, "get", None)
    if callable(getter):
        return getter(dotted_key)
    return None


def _extract_spreadsheet_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = _SPREADSHEET_ID_RE.search(text)
    if match:
        return match.group(1).strip()
    # Allow callers to provide a raw ID in config/env.
    if "/" not in text and " " not in text:
        return text
    return ""


def get_rules_management_spreadsheet_id(cfg: Any = None) -> str:
    """Return the configured Rules Management spreadsheet ID, if available."""
    env_id = _extract_spreadsheet_id(os.getenv("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID"))
    if env_id:
        return env_id

    cfg_id = _extract_spreadsheet_id(_cfg_get(cfg, "rules.management_spreadsheet_id"))
    if cfg_id:
        return cfg_id

    return _extract_spreadsheet_id(_cfg_get(cfg, "rules.management_workbook_url"))


__all__ = ["get_rules_management_spreadsheet_id"]
