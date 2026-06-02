"""Detect Register 1 shift close via findTransactions (Shift embedded on sale lines)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from lib.growflow_queries import PAGE_SIZE, fetch_paginated

TRANSACTIONS_SHIFT_QUERY = """
query Tx($first: Int, $after: String, $where: TransactionsWhereInput) {
  findTransactions(first: $first, after: $after, where: $where) {
    edges { node {
      objectId updatedAt
      Register
      Shift
    } }
    pageInfo { hasNextPage endCursor }
  }
}
"""


@dataclass(frozen=True)
class EndHourSchedule:
    """Earliest local hour (0-23) to treat a shift EndTime as end-of-day close."""

    sunday: int = 20
    mon_sat: int = 22

    def min_hour_for(self, end_local: datetime) -> int:
        # datetime.weekday(): Monday=0 … Sunday=6
        if end_local.weekday() == 6:
            return self.sunday
        return self.mon_sat

    def allows(self, end_local: datetime) -> bool:
        return end_local.hour >= self.min_hour_for(end_local)


def end_hour_schedule_from_config(cfg: dict[str, Any]) -> EndHourSchedule:
    """Build schedule from register_close_notify config (Oklahoma Central defaults)."""
    sunday = cfg.get("min_local_end_hour_sunday")
    mon_sat = cfg.get("min_local_end_hour_mon_sat")
    if sunday is None:
        sunday = cfg.get("min_local_end_hour", 20)
    if mon_sat is None:
        mon_sat = cfg.get("min_local_end_hour", 22)
    return EndHourSchedule(sunday=int(sunday), mon_sat=int(mon_sat))


@dataclass(frozen=True)
class PollWindowSchedule:
    """Local hours when scheduled polls are allowed (Central / store timezone)."""

    sunday_start: int = 20
    mon_sat_start: int = 22
    window_hours: int = 4

    def start_hour_for(self, when_local: datetime) -> int:
        if when_local.weekday() == 6:
            return self.sunday_start
        return self.mon_sat_start

    def in_window(self, when_local: datetime) -> bool:
        """True during [start, midnight) and [midnight, start+window past midnight)."""
        start = self.start_hour_for(when_local)
        end_after_midnight = self.window_hours - (24 - start)
        h = when_local.hour
        if h >= start:
            return True
        if end_after_midnight > 0 and h < end_after_midnight:
            return True
        return False


def poll_window_schedule_from_config(cfg: dict[str, Any]) -> PollWindowSchedule:
    sunday = cfg.get("poll_start_hour_sunday", cfg.get("min_local_end_hour_sunday", 20))
    mon_sat = cfg.get("poll_start_hour_mon_sat", cfg.get("min_local_end_hour_mon_sat", 22))
    hours = cfg.get("poll_window_hours", 4)
    return PollWindowSchedule(
        sunday_start=int(sunday),
        mon_sat_start=int(mon_sat),
        window_hours=int(hours),
    )


@dataclass(frozen=True)
class ClosedShiftEvent:
    shift_id: str
    register_name: str
    register_id: str
    sales_date: date
    end_time_local: datetime
    end_time_utc: datetime


def _parse_growflow_datetime(val: Any) -> datetime | None:
    if isinstance(val, dict) and val.get("iso"):
        val = val["iso"]
    if not val:
        return None
    s = str(val).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _register_info(tx: dict[str, Any]) -> tuple[str, str]:
    reg = tx.get("Register")
    if isinstance(reg, dict):
        return str(reg.get("objectId") or ""), str(reg.get("Name") or reg.get("name") or "")
    return "", ""


def _shift_register_info(shift: dict[str, Any], tx: dict[str, Any]) -> tuple[str, str]:
    reg = shift.get("Register")
    if isinstance(reg, dict) and reg.get("Name"):
        return str(reg.get("objectId") or ""), str(reg.get("Name") or "")
    return _register_info(tx)


def extract_closed_shifts(
    transactions: list[dict[str, Any]],
    *,
    tz: ZoneInfo,
    register_name: str | None = None,
    register_id: str | None = None,
    min_local_end_hour: int | None = None,
    end_hour_schedule: EndHourSchedule | None = None,
) -> list[ClosedShiftEvent]:
    """Return newly-seen closed shifts from transaction nodes (deduped by shift id)."""
    schedule = end_hour_schedule or EndHourSchedule()
    want_name = (register_name or "").strip().lower()
    want_id = (register_id or "").strip()
    seen_shift: set[str] = set()
    out: list[ClosedShiftEvent] = []

    for tx in transactions:
        shift = tx.get("Shift")
        if not isinstance(shift, dict):
            continue
        sid = str(shift.get("objectId") or "")
        if not sid or sid in seen_shift:
            continue
        seen_shift.add(sid)
        if shift.get("IsOpen"):
            continue
        end_utc = _parse_growflow_datetime(shift.get("EndTime"))
        if not end_utc:
            continue
        if end_utc.tzinfo is None:
            end_utc = end_utc.replace(tzinfo=timezone.utc)
        end_local = end_utc.astimezone(tz)
        if min_local_end_hour is not None:
            if end_local.hour < min_local_end_hour:
                continue
        elif not schedule.allows(end_local):
            continue

        reg_id, reg_name = _shift_register_info(shift, tx)
        if want_id and reg_id != want_id:
            continue
        if want_name and reg_name.strip().lower() != want_name:
            continue

        start_utc = _parse_growflow_datetime(shift.get("StartTime"))
        if start_utc is None:
            sales_day = end_local.date()
        else:
            if start_utc.tzinfo is None:
                start_utc = start_utc.replace(tzinfo=timezone.utc)
            sales_day = start_utc.astimezone(tz).date()

        out.append(
            ClosedShiftEvent(
                shift_id=sid,
                register_name=reg_name or register_name or "",
                register_id=reg_id,
                sales_date=sales_day,
                end_time_local=end_local,
                end_time_utc=end_utc,
            )
        )
    return out


def fetch_transactions_since(
    since_iso: str,
    *,
    credentials_path: str | None,
) -> list[dict[str, Any]]:
    return fetch_paginated(
        "findTransactions",
        TRANSACTIONS_SHIFT_QUERY,
        {"first": PAGE_SIZE, "where": {"updatedAt": {"greaterThanOrEqualTo": since_iso}}},
        credentials_path=credentials_path,
    )


def load_state(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"notified_shift_ids": [], "notified_sales_dates": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"notified_shift_ids": [], "notified_sales_dates": {}}
    if not isinstance(data, dict):
        return {"notified_shift_ids": [], "notified_sales_dates": {}}
    data.setdefault("notified_shift_ids", [])
    data.setdefault("notified_sales_dates", {})
    return data


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def filter_notifiable_events(
    events: list[ClosedShiftEvent],
    state: dict[str, Any],
    *,
    notify_once_per_sales_date: bool = True,
) -> list[ClosedShiftEvent]:
    notified_ids = set(state.get("notified_shift_ids") or [])
    notified_dates = state.get("notified_sales_dates") or {}
    out: list[ClosedShiftEvent] = []
    for ev in events:
        if ev.shift_id in notified_ids:
            continue
        if notify_once_per_sales_date:
            key = ev.register_name or ev.register_id or "default"
            if str(notified_dates.get(key)) == ev.sales_date.isoformat():
                continue
        out.append(ev)
    return out


def mark_notified(state: dict[str, Any], event: ClosedShiftEvent) -> None:
    ids = list(state.get("notified_shift_ids") or [])
    if event.shift_id not in ids:
        ids.append(event.shift_id)
    state["notified_shift_ids"] = ids[-500:]
    dates = dict(state.get("notified_sales_dates") or {})
    key = event.register_name or event.register_id or "default"
    dates[key] = event.sales_date.isoformat()
    state["notified_sales_dates"] = dates
    state["last_notified_at"] = datetime.now(timezone.utc).isoformat()
