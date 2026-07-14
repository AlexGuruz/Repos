from __future__ import annotations

import os
import re
from typing import Any
from urllib.parse import urlparse


_SHEETS_PATH_RE = re.compile(r"/spreadsheets/d/([^/?#]+)")


def extract_spreadsheet_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""

    parsed = urlparse(text)
    match = _SHEETS_PATH_RE.search(parsed.path)
    if match:
        return match.group(1).strip()

    return text


def _cfg_get(cfg: Any, dotted_key: str, default: Any = None) -> Any:
    if cfg is None:
        return default

    getter = getattr(cfg, "get", None)
    if callable(getter):
        try:
            value = getter(dotted_key, default)
            if value is not default:
                return value
        except TypeError:
            try:
                value = getter(dotted_key)
                if value is not None:
                    return value
            except Exception:
                pass
        except Exception:
            pass

    data = getattr(cfg, "data", cfg)
    cur = data
    for part in dotted_key.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return cur


def _load_config_best_effort() -> Any:
    try:
        from services.common.config_loader import load_config

        return load_config()
    except Exception:
        return None


def get_rules_management_spreadsheet_id(cfg: Any = None) -> str:
    env_value = os.environ.get("KYLO_RULES_MANAGEMENT_SPREADSHEET_ID")
    if env_value:
        return extract_spreadsheet_id(env_value)

    effective_cfg = cfg if cfg is not None else _load_config_best_effort()
    for key in ("rules.management_spreadsheet_id", "rules.management_workbook_url"):
        value = _cfg_get(effective_cfg, key)
        sid = extract_spreadsheet_id(value)
        if sid:
            return sid

    return ""


__all__ = ["extract_spreadsheet_id", "get_rules_management_spreadsheet_id"]
