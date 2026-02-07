from __future__ import annotations

import hashlib
import os
import time
from typing import Dict, List

from services.common.config_loader import load_config
from services.sheets.poster import _extract_spreadsheet_id, _get_service
from services.rules.jgdtruth_provider import fetch_rules_from_jgdtruth


def _rules_checksum(rules: Dict[str, object]) -> str:
    # stable over approved subset: (source,target_sheet,target_header,approved)
    payload: List[str] = []
    for src, r in sorted(rules.items()):
        try:
            row = (getattr(r, "source", ""), getattr(r, "target_sheet", ""), getattr(r, "target_header", ""), getattr(r, "approved", False))
        except Exception:
            continue
        if not row[3]:
            continue
        payload.append("|".join([row[0], row[1], row[2], "TRUE"]))
    blob = "\n".join(payload)
    return hashlib.md5(blob.encode("utf-8")).hexdigest()


def watch_and_post(company: str, interval_seconds: int = 60) -> None:
    # Read company workbook id for posting sanity check (not used directly here)
    cfg = load_config()
    companies = cfg.get("sheets.companies") or []
    if not any((it.get("key") or "").strip().upper() == company.upper() for it in companies):
        raise SystemExit(f"Unknown company: {company}")

    last = None
    while True:
        rules = fetch_rules_from_jgdtruth(company)
        sig = _rules_checksum(rules)
        if sig != last:
            # Trigger a run for this company
            try:
                from bin.sort_and_post_from_jgdtruth import run as sort_post_run
                sort_post_run(company)
            except Exception as e:
                # Soft-fail and continue polling
                pass
            last = sig
        time.sleep(max(10, int(interval_seconds)))


__all__ = ["watch_and_post"]



