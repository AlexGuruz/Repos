"""
Time context tool (Guru §21, PDR Phase 2.75). Returns current date/time in user timezone.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo


def get_time_context(timezone_name: str = "America/Chicago") -> dict[str, Any]:
    """
    Return current date/time context in the given timezone.
    Use America/Chicago by default for correct "today" / scheduling.
    """
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("America/Chicago")
    now = datetime.now(tz)
    return {
        "current_date": now.strftime("%Y-%m-%d"),
        "current_datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "timezone": timezone_name,
        "today_label": now.strftime("%A, %B %d, %Y"),
        "week_label": now.strftime("%Y-W%W"),
    }
