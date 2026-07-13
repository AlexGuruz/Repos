from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from services.intake.csv_downloader import download_petty_cash_csv
from services.intake.csv_processor import PettyCashCSVProcessor
from services.sheets.poster import _extract_spreadsheet_id


class IntakeLoadError(RuntimeError):
    """Raised when audit intake cannot load the full expected workbook/tab set."""


def _active_years(cfg) -> Optional[List[int]]:
    import os

    raw = (os.environ.get("KYLO_ACTIVE_YEARS") or "").strip()
    if raw:
        years: List[int] = []
        for part in re.split(r"[,\s]+", raw):
            if part and str(part).strip().isdigit():
                years.append(int(part))
        return years or None
    cfg_val = cfg.get("year_workbooks_active")
    if isinstance(cfg_val, list) and cfg_val:
        years = []
        for it in cfg_val:
            try:
                years.append(int(str(it).strip()))
            except Exception:
                continue
        return years or None
    ym = cfg.get("year_workbooks") or {}
    if isinstance(ym, dict) and ym:
        years = []
        for k in ym.keys():
            try:
                years.append(int(str(k).strip()))
            except Exception:
                continue
        return years or None
    return None


def intake_urls_for_company(cfg, company: str) -> List[str]:
    companies = cfg.get("sheets.companies") or []
    comp = next((it for it in companies if (it.get("key") or "").strip().upper() == company.strip().upper()), None)
    if not comp:
        return []
    urls: List[str] = []
    active = _active_years(cfg)
    ym = cfg.get("year_workbooks") or {}
    if isinstance(ym, dict):
        for y, spec in ym.items():
            try:
                yi = int(str(y).strip())
            except Exception:
                continue
            if active and yi not in active:
                continue
            if isinstance(spec, dict):
                u = spec.get("intake_workbook_url")
            else:
                u = cfg.get(f"year_workbooks.{yi}.intake_workbook_url")
            if u and str(u).strip():
                urls.append(str(u).strip())
    if not urls:
        intake_url = cfg.get("intake.workbook_url") or comp.get("workbook_url")
        if intake_url:
            urls.append(str(intake_url))
    return urls


def load_intake_for_company(
    cfg,
    company: str,
    *,
    service_account: Optional[str] = None,
) -> Tuple[List[dict], Dict[str, str]]:
    """Load parsed transactions and raw CSV content per tab key."""
    sa = service_account or cfg.get("google.service_account_json_path") or ""
    extra_tabs: List[str] = []
    try:
        extra_tabs = [str(t) for t in (cfg.get("intake.extra_tabs") or []) if str(t).strip()]
    except Exception:
        extra_tabs = []
    tabs = tuple(["TRANSACTIONS", "BANK"]) + tuple(extra_tabs)
    header_rows = int(cfg.get("intake.csv_processor.header_rows", 19))

    txns: List[dict] = []
    csv_by_key: Dict[str, str] = {}
    failures: List[str] = []
    urls = intake_urls_for_company(cfg, company)
    if not urls:
        raise IntakeLoadError(f"no intake workbook configured for {company}")
    for url in urls:
        sid = _extract_spreadsheet_id(str(url))
        if not sid:
            failures.append(f"{company}:invalid_intake_url")
            continue
        for tab in tabs:
            key = f"{sid}|{tab.upper()}"
            try:
                csv_content = download_petty_cash_csv(sid, sa, sheet_name_override=tab)
                csv_by_key[key] = csv_content
                processor = PettyCashCSVProcessor(
                    csv_content,
                    header_rows=header_rows,
                    source_tab=tab,
                    source_spreadsheet_id=sid,
                )
                part = list(processor.parse_transactions())
                for it in part:
                    if (it.get("company_id") or "").strip().upper() != company.strip().upper():
                        continue
                    it["source_tab"] = tab
                    it["source_spreadsheet_id"] = sid
                    txns.append(it)
            except Exception as e:
                failures.append(f"{key}: {type(e).__name__}: {e}")
    if failures:
        raise IntakeLoadError("partial intake load blocked; failed tabs: " + "; ".join(failures[:8]))
    return txns, csv_by_key


def load_all_intake(
    cfg,
    companies: List[str],
    *,
    service_account: Optional[str] = None,
) -> Tuple[List[dict], Dict[str, str]]:
    all_txns: List[dict] = []
    all_csv: Dict[str, str] = {}
    for cid in companies:
        txns, csv_map = load_intake_for_company(cfg, cid, service_account=service_account)
        all_txns.extend(txns)
        all_csv.update(csv_map)
    return all_txns, all_csv


__all__ = ["IntakeLoadError", "intake_urls_for_company", "load_all_intake", "load_intake_for_company"]
