from __future__ import annotations

import os
import re
from typing import Any, Optional

from services.common.config_loader import load_config


def _cfg_get(cfg: Any, dotted: str) -> Optional[str]:
    if cfg is None or not hasattr(cfg, "get"):
        return None
    try:
        value = cfg.get(dotted)
    except TypeError:
        value = None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _extract_spreadsheet_id(value: str | None) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", text)
    if match:
        return match.group(1)
    if re.fullmatch(r"[a-zA-Z0-9-_]{20,}", text):
        return text
    return None


def get_rules_management_spreadsheet_id(cfg: Any = None) -> Optional[str]:
    """Resolve the rules-management Google spreadsheet ID from env or config."""
    for env_name in (
        "KYLO_RULES_MANAGEMENT_SPREADSHEET_ID",
        "KYLO_RULES_MANAGEMENT_WORKBOOK_URL",
    ):
        sid = _extract_spreadsheet_id(os.environ.get(env_name))
        if sid:
            return sid

    if cfg is None:
        try:
            cfg = load_config()
        except Exception:
            cfg = None

    for key in ("rules.management_spreadsheet_id", "rules.management_workbook_url"):
        sid = _extract_spreadsheet_id(_cfg_get(cfg, key))
        if sid:
            return sid
    return None


__all__ = ["get_rules_management_spreadsheet_id"]
