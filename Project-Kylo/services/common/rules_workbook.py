from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlparse


_SHEETS_ID_RE = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]+)")


def _cfg_get(cfg: Any, dotted_key: str) -> Any:
    if cfg is None:
        return None
    if hasattr(cfg, "get"):
        try:
            return cfg.get(dotted_key)
        except TypeError:
            pass
    cur = cfg
    for part in dotted_key.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def spreadsheet_id_from_url(url: str | None) -> str | None:
    text = str(url or "").strip()
    if not text:
        return None
    match = _SHEETS_ID_RE.search(text)
    if match:
        return match.group(1)
    parsed = urlparse(text)
    if parsed.netloc and parsed.path:
        return None
    return text if "/" not in text else None


def get_rules_management_spreadsheet_id(cfg: Any = None) -> str | None:
    env_id = os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID")
    if env_id and env_id.strip():
        return env_id.strip()

    direct = _cfg_get(cfg, "rules.management_spreadsheet_id")
    if direct and str(direct).strip():
        return str(direct).strip()

    url = _cfg_get(cfg, "rules.management_workbook_url")
    return spreadsheet_id_from_url(str(url) if url else None)


__all__ = ["get_rules_management_spreadsheet_id", "spreadsheet_id_from_url"]
