#!/usr/bin/env python3
"""Poll GrowFlow for Register 1 close; write daily tax totals to Google Sheet Taxes tab."""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from lib.daily_close_report import build_daily_close_report, format_daily_close_telegram
from lib.growflow_config import apply_growflow_env, load_config
from lib.register_shift_watch import (
    end_hour_schedule_from_config,
    extract_closed_shifts,
    fetch_transactions_since,
    filter_notifiable_events,
    load_state,
    mark_notified,
    poll_window_schedule_from_config,
    resolve_transaction_poll_since,
    save_state,
)
from lib.taxes_sheet_export import resolve_taxes_sheet_config, write_taxes_to_sheet


def _resolve_tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("America/Chicago")


def _parse_date(s: str) -> date:
    y, m, d = map(int, s.split("-"))
    return date(y, m, d)


def _export_for_date(
    sales_date: date,
    *,
    cfg: dict,
    tz: ZoneInfo,
    shift_end_local: datetime | None,
    dry_run: bool,
) -> None:
    report = build_daily_close_report(
        sales_date,
        credentials_path=cfg.get("credentials_path"),
        tz=tz,
        shift_end_local=shift_end_local,
        register_name=str(cfg.get("register_name") or "Register 1"),
    )
    print(format_daily_close_telegram(report), flush=True)
    sheet_cfg = resolve_taxes_sheet_config(cfg)
    update_range = write_taxes_to_sheet(
        report,
        spreadsheet_id=str(sheet_cfg["spreadsheet_id"]),
        sheet_name=str(sheet_cfg["sheet_name"]),
        service_account_path=sheet_cfg.get("service_account_path"),
        dry_run=dry_run,
    )
    if dry_run:
        print(f"(dry-run: would update {update_range})", flush=True)
    else:
        print(f"Updated sheet range {update_range}", flush=True)


def _append_log(message: str, cfg: dict) -> None:
    log_path = Path(str(cfg.get("state_path", ""))).parent.parent / "logs" / "register_close_taxes.log"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"[{ts}] {message}\n")
    except OSError:
        pass


def _poll_once(cfg: dict, tz: ZoneInfo, *, dry_run: bool, lookback_hours: int) -> int:
    state_path = Path(str(cfg.get("state_path")))
    state = load_state(state_path)
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(tz)
    since_dt = resolve_transaction_poll_since(
        now_utc=now_utc,
        now_local=now_local,
        last_poll_at=state.get("last_poll_at"),
        lookback_hours=lookback_hours,
        poll_window=poll_window_schedule_from_config(cfg),
    )
    since = since_dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

    txs = fetch_transactions_since(since, credentials_path=cfg.get("credentials_path"))
    events = extract_closed_shifts(
        txs,
        tz=tz,
        register_name=str(cfg.get("register_name") or "Register 1"),
        register_id=str(cfg.get("register_object_id") or "") or None,
        end_hour_schedule=end_hour_schedule_from_config(cfg),
    )
    pending = filter_notifiable_events(
        events,
        state,
        notify_once_per_sales_date=bool(cfg.get("notify_once_per_sales_date", True)),
    )
    exported = 0
    for ev in sorted(pending, key=lambda e: e.end_time_utc):
        print(
            f"Register close detected: shift={ev.shift_id} sales_date={ev.sales_date} "
            f"end_local={ev.end_time_local.isoformat()}",
            flush=True,
        )
        _append_log(
            f"Register close shift={ev.shift_id} date={ev.sales_date} end={ev.end_time_local.isoformat()}",
            cfg,
        )
        try:
            _export_for_date(
                ev.sales_date, cfg=cfg, tz=tz, shift_end_local=ev.end_time_local, dry_run=dry_run
            )
        except Exception as e:
            _append_log(f"Export FAILED for {ev.sales_date}: {e}", cfg)
            print(f"Export FAILED for {ev.sales_date}: {e}", file=sys.stderr, flush=True)
            continue
        if not dry_run:
            mark_notified(state, ev)
            exported += 1
            _append_log(f"Exported taxes for {ev.sales_date} to Google Sheet", cfg)

    state["last_poll_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    if not dry_run:
        save_state(state_path, state)
    return exported


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Write Taxes sheet when Register 1 closes in GrowFlow."
    )
    ap.add_argument("--config", type=Path, default=_root / "config" / "config.yaml")
    ap.add_argument("--poll", action="store_true", help="Poll continuously (default if no other mode)")
    ap.add_argument("--once", action="store_true", help="Single poll cycle (for Task Scheduler)")
    ap.add_argument("--export-for-date", metavar="YYYY-MM-DD", help="Export taxes for a date immediately")
    ap.add_argument("--dry-run", action="store_true", help="Print report; do not write sheet or update state")
    ap.add_argument("--poll-interval", type=int, default=None, help="Seconds between polls (default from config)")
    ap.add_argument("--lookback-hours", type=int, default=36, help="First-run transaction lookback window")
    args = ap.parse_args()

    cfg = load_config(args.config)
    apply_growflow_env(cfg)
    tz = _resolve_tz(str(cfg.get("sales_timezone") or "America/Chicago"))

    if args.export_for_date:
        _export_for_date(
            _parse_date(args.export_for_date),
            cfg=cfg,
            tz=tz,
            shift_end_local=None,
            dry_run=args.dry_run,
        )
        return 0

    interval = args.poll_interval if args.poll_interval is not None else int(cfg.get("poll_interval_seconds") or 120)
    continuous = args.poll or not args.once

    if args.once:
        window = poll_window_schedule_from_config(cfg)
        now_local = datetime.now(tz)
        if not window.in_window(now_local) and not args.dry_run:
            # Outside EOD poll window — exit quietly (Task Scheduler only fires in-window anyway).
            return 0
        _poll_once(cfg, tz, dry_run=args.dry_run, lookback_hours=args.lookback_hours)
        return 0

    schedule = end_hour_schedule_from_config(cfg)
    print(
        f"Watching for {cfg.get('register_name')} close (poll every {interval}s, "
        f"tz={tz.key if hasattr(tz, 'key') else tz}, "
        f"Sun>={schedule.sunday}:00, Mon-Sat>={schedule.mon_sat}:00 local)",
        flush=True,
    )
    while True:
        try:
            n = _poll_once(cfg, tz, dry_run=args.dry_run, lookback_hours=args.lookback_hours)
            if n:
                print(f"Exported {n} day(s) to sheet.", flush=True)
        except KeyboardInterrupt:
            print("Stopped.", flush=True)
            return 0
        except Exception as e:
            print(f"Poll error: {e}", file=sys.stderr, flush=True)
        if not continuous:
            break
        time.sleep(interval)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
