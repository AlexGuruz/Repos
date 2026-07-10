"""Load GrowFlow + sheet export settings from config/config.yaml (no PyYAML)."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent


def _yaml_scalar(text: str, key: str) -> str | None:
    m = re.search(rf"^\s*{re.escape(key)}:\s*[\"']?([^\"'#\n]+)", text, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip().strip("\"'")


def _yaml_block(text: str, section: str) -> str:
    m = re.search(rf"^\s*{re.escape(section)}:\s*\n((?:[ \t]+[^\n]+\n?)*)", text, re.MULTILINE)
    return m.group(1) if m else ""


def load_config(path: Path | None = None) -> dict[str, Any]:
    p = path or REPO_ROOT / "config" / "config.yaml"
    out: dict[str, Any] = {
        "credentials_path": None,
        "org_id": None,
        "sales_timezone": "America/Chicago",
        "register_name": "Register 1",
        "register_object_id": None,
        "min_local_end_hour_sunday": 20,
        "min_local_end_hour_mon_sat": 22,
        "poll_start_hour_sunday": 20,
        "poll_start_hour_mon_sat": 22,
        "poll_window_hours": 4,
        "poll_interval_minutes": 5,
        "notify_once_per_sales_date": True,
        "poll_interval_seconds": 300,
        "state_path": str(REPO_ROOT / "data" / "register_close_taxes_state.json"),
        "taxes_spreadsheet_id": None,
        "taxes_sheet_name": "Taxes",
        "taxes_sheet_service_account_path": None,
        "google_sheets": {},
        "taxes_sheet": {},
        "balance_misc_snapshot": {},
        "petty_cash_snapshot": {},
    }
    if not p.is_file():
        return out
    text = p.read_text(encoding="utf-8", errors="replace")
    gf = _yaml_block(text, "growflow")
    gs = _yaml_block(text, "google_sheets")
    ts = _yaml_block(text, "taxes_sheet")
    bms = _yaml_block(text, "balance_misc_snapshot")
    pcs = _yaml_block(text, "petty_cash_snapshot")
    rc = _yaml_block(text, "register_close_notify")

    out["credentials_path"] = _yaml_scalar(text, "credentials_path") or _yaml_scalar(gf, "credentials_path")
    out["org_id"] = _yaml_scalar(text, "org_id") or _yaml_scalar(gf, "org_id")
    out["sales_timezone"] = _yaml_scalar(text, "sales_timezone") or _yaml_scalar(gf, "sales_timezone") or out["sales_timezone"]

    out["google_sheets"] = {
        "service_account_path": _yaml_scalar(gs, "service_account_path"),
        "spreadsheet_id": _yaml_scalar(gs, "spreadsheet_id"),
    }
    out["taxes_sheet"] = {
        "spreadsheet_id": _yaml_scalar(ts, "spreadsheet_id"),
        "sheet_name": _yaml_scalar(ts, "sheet_name") or "Taxes",
        "service_account_path": _yaml_scalar(ts, "service_account_path"),
    }
    out["taxes_spreadsheet_id"] = out["taxes_sheet"].get("spreadsheet_id")
    out["taxes_sheet_name"] = out["taxes_sheet"].get("sheet_name")
    out["taxes_sheet_service_account_path"] = out["taxes_sheet"].get("service_account_path")

    out["balance_misc_snapshot"] = {
        "spreadsheet_id": _yaml_scalar(bms, "spreadsheet_id"),
        "sheet_name": _yaml_scalar(bms, "sheet_name") or "Balance and Misc",
        "sheet_id": _yaml_scalar(bms, "sheet_id"),
        "service_account_path": _yaml_scalar(bms, "service_account_path"),
        "snapshot_tab_prefix": _yaml_scalar(bms, "snapshot_tab_prefix"),
        "timezone": _yaml_scalar(bms, "timezone"),
        "max_snapshots": _yaml_scalar(bms, "max_snapshots"),
        "local_snapshot_dir": _yaml_scalar(bms, "local_snapshot_dir"),
        "write_local_json": _yaml_scalar(bms, "write_local_json"),
        "change_log_dir": _yaml_scalar(bms, "change_log_dir"),
        "max_change_log_days": _yaml_scalar(bms, "max_change_log_days"),
    }

    out["petty_cash_snapshot"] = {
        "spreadsheet_id": _yaml_scalar(pcs, "spreadsheet_id"),
        "sheet_name": _yaml_scalar(pcs, "sheet_name") or "PETTY CASH",
        "sheet_id": _yaml_scalar(pcs, "sheet_id"),
        "service_account_path": _yaml_scalar(pcs, "service_account_path"),
        "snapshot_tab_prefix": _yaml_scalar(pcs, "snapshot_tab_prefix"),
        "timezone": _yaml_scalar(pcs, "timezone"),
        "max_snapshots": _yaml_scalar(pcs, "max_snapshots"),
        "local_snapshot_dir": _yaml_scalar(pcs, "local_snapshot_dir"),
        "write_local_json": _yaml_scalar(pcs, "write_local_json"),
        "change_log_dir": _yaml_scalar(pcs, "change_log_dir"),
        "max_change_log_days": _yaml_scalar(pcs, "max_change_log_days"),
    }

    out["register_name"] = _yaml_scalar(rc, "register_name") or out["register_name"]
    out["register_object_id"] = _yaml_scalar(rc, "register_object_id")
    sun = _yaml_scalar(rc, "min_local_end_hour_sunday")
    if sun is not None:
        try:
            out["min_local_end_hour_sunday"] = int(sun)
        except ValueError:
            pass
    mon = _yaml_scalar(rc, "min_local_end_hour_mon_sat")
    if mon is not None:
        try:
            out["min_local_end_hour_mon_sat"] = int(mon)
        except ValueError:
            pass
    min_hour = _yaml_scalar(rc, "min_local_end_hour")
    if min_hour is not None:
        try:
            out["min_local_end_hour"] = int(min_hour)
        except ValueError:
            pass
    once = _yaml_scalar(rc, "notify_once_per_sales_date")
    if once is not None:
        out["notify_once_per_sales_date"] = once.lower() not in {"0", "false", "no"}
    interval = _yaml_scalar(rc, "poll_interval_seconds")
    if interval is not None:
        try:
            out["poll_interval_seconds"] = int(interval)
        except ValueError:
            pass
    for key, out_key in (
        ("poll_start_hour_sunday", "poll_start_hour_sunday"),
        ("poll_start_hour_mon_sat", "poll_start_hour_mon_sat"),
        ("poll_window_hours", "poll_window_hours"),
        ("poll_interval_minutes", "poll_interval_minutes"),
    ):
        val = _yaml_scalar(rc, key)
        if val is not None:
            try:
                out[out_key] = int(val)
            except ValueError:
                pass
    state = _yaml_scalar(rc, "state_path")
    if state:
        out["state_path"] = state
    return out


def apply_growflow_env(cfg: dict[str, Any]) -> None:
    if not (os.environ.get("GROWFLOW_RETAIL_ORG") or "").strip() and cfg.get("org_id"):
        os.environ["GROWFLOW_RETAIL_ORG"] = str(cfg["org_id"])
