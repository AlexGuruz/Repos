from __future__ import annotations

import os
import re
from typing import Any


_SPREADSHEET_RE = re.compile(r"/spreadsheets/d/([^/?#]+)")


def _cfg_get(cfg: Any, dotted_key: str) -> Any:
    if cfg is None:
        return None
    getter = getattr(cfg, "get", None)
    if callable(getter):
        return getter(dotted_key)
    cur = cfg
    for part in dotted_key.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def extract_spreadsheet_id(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = _SPREADSHEET_RE.search(text)
    if match:
        return match.group(1).strip()
    return text


def get_rules_management_spreadsheet_id(cfg: Any = None) -> str:
    """Resolve the dedicated rules-management spreadsheet ID from env or config."""
    env_id = extract_spreadsheet_id(os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID"))
    if env_id:
        return env_id

    if cfg is None:
        try:
            from services.common.config_loader import load_config

            cfg = load_config()
        except Exception:
            cfg = None

    cfg_id = extract_spreadsheet_id(_cfg_get(cfg, "rules.management_spreadsheet_id"))
    if cfg_id:
        return cfg_id

    return extract_spreadsheet_id(_cfg_get(cfg, "rules.management_workbook_url"))


__all__ = ["extract_spreadsheet_id", "get_rules_management_spreadsheet_id"]
