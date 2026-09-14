from __future__ import annotations

import os
from typing import Any, Optional

from services.common.config_loader import load_config


def _extract_spreadsheet_id(value: str) -> str:
    text = str(value or "").strip()
    if "/spreadsheets/d/" in text:
        try:
            return text.split("/spreadsheets/d/", 1)[1].split("/", 1)[0]
        except Exception:
            return text
    return text


def _cfg_get(cfg: Any, dotted: str) -> Optional[str]:
    if cfg is None or not hasattr(cfg, "get"):
        return None
    try:
        value = cfg.get(dotted)
    except Exception:
        return None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def get_rules_management_spreadsheet_id(cfg: Any = None) -> str:
    """Resolve the JGDTruth/rules-management spreadsheet ID from env or config."""
    explicit = (
        os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID")
        or os.environ.get("KYLO_RULES_MANAGEMENT_WORKBOOK_ID")
        or ""
    ).strip()
    if explicit:
        return _extract_spreadsheet_id(explicit)

    workbook = (os.environ.get("KYLO_RULES_MANAGEMENT_WORKBOOK_URL") or "").strip()
    if workbook:
        return _extract_spreadsheet_id(workbook)

    if cfg is None:
        try:
            cfg = load_config()
        except Exception:
            cfg = None

    configured_id = _cfg_get(cfg, "rules.management_spreadsheet_id")
    if configured_id:
        return _extract_spreadsheet_id(configured_id)

    configured_url = _cfg_get(cfg, "rules.management_workbook_url")
    if configured_url:
        return _extract_spreadsheet_id(configured_url)

    return ""


__all__ = ["get_rules_management_spreadsheet_id"]
