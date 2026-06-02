"""Tests for register close Telegram report helpers."""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from lib.daily_close_report import DailyCloseReport, format_daily_close_telegram
from lib.register_shift_watch import (
    EndHourSchedule,
    PollWindowSchedule,
    ClosedShiftEvent,
    end_hour_schedule_from_config,
    extract_closed_shifts,
    filter_notifiable_events,
    poll_window_schedule_from_config,
)


def test_format_daily_close_telegram_includes_totals():
    report = DailyCloseReport(
        sales_date=date(2026, 6, 1),
        timezone_label="America/Chicago",
        order_count=64,
        total_collected_cents=241489,
        subtotal_cents=257530,
        discounts_cents=16041,
        taxes_cents=34213,
        tender_cents={"CASH": 95273, "OTHER": 129966, "SPLIT": 16250},
        mj_tax_cents=13752,
        sales_tax_cents=20461,
        shift_end_local=datetime(2026, 6, 1, 22, 4, tzinfo=ZoneInfo("America/Chicago")),
        register_name="Register 1",
    )
    text = format_daily_close_telegram(report)
    assert "Total collected: $2,414.89" in text
    assert "Cash: $952.73" in text
    assert "Sales:         $204.61" in text
    assert "TOTAL TO HOLD: $350.40" in text


def test_extract_closed_shifts_register_1_only():
    tz = ZoneInfo("America/Chicago")
    txs = [
        {
            "Register": {"objectId": "r1", "Name": "Register 1"},
            "Shift": {
                "objectId": "shift1",
                "IsOpen": False,
                "EndTime": {"iso": "2026-06-02T03:04:29.641Z"},
                "StartTime": {"iso": "2026-06-01T12:55:40.319Z"},
                "Register": {"objectId": "r1", "Name": "Register 1"},
            },
        },
        {
            "Register": {"objectId": "r2", "Name": "Register 2"},
            "Shift": {
                "objectId": "shift2",
                "IsOpen": False,
                "EndTime": {"iso": "2026-06-02T03:04:29.641Z"},
                "StartTime": {"iso": "2026-06-01T12:55:40.319Z"},
            },
        },
    ]
    events = extract_closed_shifts(
        txs, tz=tz, register_name="Register 1", end_hour_schedule=EndHourSchedule(sunday=20, mon_sat=22)
    )
    assert len(events) == 1
    assert events[0].shift_id == "shift1"
    assert events[0].sales_date == date(2026, 6, 1)


def test_end_hour_schedule_sunday_vs_monday():
    tz = ZoneInfo("America/Chicago")
    schedule = EndHourSchedule(sunday=20, mon_sat=22)

    def _tx(end_iso: str) -> dict:
        return {
            "Register": {"objectId": "r1", "Name": "Register 1"},
            "Shift": {
                "objectId": "x",
                "IsOpen": False,
                "EndTime": {"iso": end_iso},
                "StartTime": {"iso": "2026-06-01T12:00:00.000Z"},
            },
        }

    # Sunday 6/7/2026 7:30 PM CT -> too early (before 8 PM)
    sun_early = extract_closed_shifts(
        [_tx("2026-06-08T00:30:00.000Z")],
        tz=tz,
        register_name="Register 1",
        end_hour_schedule=schedule,
    )
    assert sun_early == []

    # Sunday 6/7/2026 8:15 PM CT -> OK
    sun_ok = extract_closed_shifts(
        [_tx("2026-06-08T01:15:00.000Z")],
        tz=tz,
        register_name="Register 1",
        end_hour_schedule=schedule,
    )
    assert len(sun_ok) == 1

    # Monday 6/8/2026 9:45 PM CT -> too early (before 10 PM)
    mon_early = extract_closed_shifts(
        [_tx("2026-06-09T02:45:00.000Z")],
        tz=tz,
        register_name="Register 1",
        end_hour_schedule=schedule,
    )
    assert mon_early == []

    # Monday 6/8/2026 10:05 PM CT -> OK
    mon_ok = extract_closed_shifts(
        [_tx("2026-06-09T03:05:00.000Z")],
        tz=tz,
        register_name="Register 1",
        end_hour_schedule=schedule,
    )
    assert len(mon_ok) == 1


def test_filter_notifiable_once_per_sales_date():
    ev = ClosedShiftEvent(
        shift_id="s1",
        register_name="Register 1",
        register_id="r1",
        sales_date=date(2026, 6, 1),
        end_time_local=datetime(2026, 6, 1, 22, 4, tzinfo=ZoneInfo("America/Chicago")),
        end_time_utc=datetime(2026, 6, 2, 3, 4, tzinfo=timezone.utc),
    )
    state = {"notified_shift_ids": [], "notified_sales_dates": {"Register 1": "2026-06-01"}}
    assert filter_notifiable_events([ev], state, notify_once_per_sales_date=True) == []


def test_poll_window_mon_sat_starts_at_10pm():
    tz = ZoneInfo("America/Chicago")
    w = PollWindowSchedule(sunday_start=20, mon_sat_start=22, window_hours=4)
    # Monday 9:59 PM — outside
    assert not w.in_window(datetime(2026, 6, 8, 21, 59, tzinfo=tz))
    # Monday 10:00 PM — inside
    assert w.in_window(datetime(2026, 6, 8, 22, 0, tzinfo=tz))
    # Tuesday 1:30 AM — still inside (10 PM + 4h window)
    assert w.in_window(datetime(2026, 6, 9, 1, 30, tzinfo=tz))
    # Tuesday 2:30 AM — outside
    assert not w.in_window(datetime(2026, 6, 9, 2, 30, tzinfo=tz))


def test_poll_window_sunday_starts_at_8pm():
    tz = ZoneInfo("America/Chicago")
    w = PollWindowSchedule(sunday_start=20, mon_sat_start=22, window_hours=4)
    assert not w.in_window(datetime(2026, 6, 7, 19, 30, tzinfo=tz))
    assert w.in_window(datetime(2026, 6, 7, 20, 0, tzinfo=tz))
