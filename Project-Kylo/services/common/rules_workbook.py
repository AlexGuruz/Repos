from __future__ import annotations

import os
from typing import Any


def _config_get(cfg: Any, dotted_key: str) -> Any:
    if cfg is None:
        return None
    if isinstance(cfg, dict):
        cur = cfg
        for part in dotted_key.split("."):
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                return None
        return cur
    getter = getattr(cfg, "get", None)
    if callable(getter):
        try:
            return getter(dotted_key)
        except TypeError:
            pass
    return None


def _extract_spreadsheet_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"none", "null"}:
        return ""
    for marker in ("/spreadsheets/d/", "/d/"):
        if marker in text:
            try:
                return text.split(marker, 1)[1].split("/", 1)[0].strip()
            except Exception:
                return text
    return text


def get_rules_management_spreadsheet_id(cfg: Any = None) -> str:
    """
    Resolve the rules-management workbook ID from runtime overrides or Kylo config.

    Accepts either a raw spreadsheet ID or a full Google Sheets URL.  When cfg is
    omitted, load the active Kylo config so services that only need this helper do
    not have to duplicate config resolution.
    """

    candidates = [
        os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID"),
        os.environ.get("KYLO_RULES_MANAGEMENT_WORKBOOK_URL"),
        _config_get(cfg, "rules.management_spreadsheet_id"),
        _config_get(cfg, "rules.management_workbook_url"),
    ]
    if cfg is None:
        try:
            from services.common.config_loader import load_config

            loaded = load_config()
        except Exception:
            loaded = None
        candidates.insert(1, _config_get(loaded, "rules.management_spreadsheet_id"))
        candidates.insert(2, _config_get(loaded, "rules.management_workbook_url"))

    for value in candidates:
        sid = _extract_spreadsheet_id(value)
        if sid:
            return sid
    return ""


__all__ = ["get_rules_management_spreadsheet_id"]
