from __future__ import annotations

import os
import re
from typing import Any


_SPREADSHEET_ID_RE = re.compile(r"/spreadsheets/d/([^/#?]+)")


def _cfg_get(cfg: Any, dotted_key: str) -> Any:
    if cfg is None:
        return None
    cur = cfg
    if not isinstance(cur, dict):
        getter = getattr(cfg, "get", None)
        if callable(getter):
            return getter(dotted_key)
        return None
    for part in dotted_key.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def extract_spreadsheet_id(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    match = _SPREADSHEET_ID_RE.search(raw)
    if match:
        return match.group(1).strip()
    return raw.split("#", 1)[0].split("?", 1)[0].strip()


def get_rules_management_spreadsheet_id(cfg: Any | None = None) -> str | None:
    if cfg is None:
        try:
            from services.common.config_loader import load_config

            cfg = load_config()
        except Exception:
            cfg = None

    candidates = (
        os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID"),
        os.environ.get("KYLO_RULES_MANAGEMENT_WORKBOOK_URL"),
        _cfg_get(cfg, "rules.management_spreadsheet_id"),
        _cfg_get(cfg, "rules.management_workbook_url"),
    )
    for candidate in candidates:
        sid = extract_spreadsheet_id(candidate)
        if sid:
            return sid
    return None


__all__ = ["extract_spreadsheet_id", "get_rules_management_spreadsheet_id"]
