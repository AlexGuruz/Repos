#!/usr/bin/env python3
"""
Print Google calendars and upcoming events so you can see IDs, titles, and time format.

First run opens a browser OAuth consent (Calendar scope only); token saved to
GOOGLE_CALENDAR_TOKEN_FILE or token.calendar.json next to credentials.

  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib

  set GOOGLE_CREDENTIALS_FILE=E:\\Repos\\ai-lab\\secrets\\gmail\\credentials.json
  python scripts/personal_ops_calendar_snapshot.py --days 14
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))


def main() -> int:
    ap = argparse.ArgumentParser(description="Google Calendar snapshot (read).")
    ap.add_argument("--days", type=int, default=14, help="Horizon in days from now for events.")
    ap.add_argument("--calendar-id", default="primary", help="Calendar ID (default: primary).")
    ap.add_argument("--list-calendars", action="store_true", help="Print calendar list and exit.")
    ap.add_argument(
        "--schema-sample",
        action="store_true",
        help="Print one full event resource (description truncated) for AI/schema mapping.",
    )
    args = ap.parse_args()

    from lib.google_calendar_client import get_calendar_service, list_calendars, list_events, preflight_calendar_auth

    pre = preflight_calendar_auth()
    if not pre["ok"]:
        print(json.dumps({"preflight": pre}, indent=2))
        print("Fix credentials path, then re-run.", file=sys.stderr)
        return 1

    svc = get_calendar_service()
    if args.list_calendars:
        try:
            cals = list_calendars(svc)
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "error": str(exc),
                        "hint": "If you see insufficient authentication scopes, delete your "
                        "Calendar token file and re-run so OAuth includes calendar.readonly "
                        "(see lib/google_calendar_client.py CALENDAR_SCOPES).",
                    },
                    indent=2,
                )
            )
            return 1
        print(json.dumps(cals, indent=2))
        return 0

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=args.days)
    tfmt = "%Y-%m-%dT%H:%M:%SZ"
    events = list_events(
        svc,
        args.calendar_id,
        time_min=now.strftime(tfmt),
        time_max=end.strftime(tfmt),
        max_results=200,
    )
    if args.schema_sample and events:
        ev0 = next((e for e in events if (e.get("description") or "").strip()), events[0])
        full = svc.events().get(calendarId=args.calendar_id, eventId=ev0["id"]).execute()
        if len(full.get("description") or "") > 1500:
            full = dict(full)
            full["description"] = (full["description"][:1500] + "\n... [truncated for snapshot]")
        print(json.dumps(full, indent=2, default=str))
        return 0

    slim = []
    for ev in events:
        start = ev.get("start", {})
        s = start.get("dateTime") or start.get("date") or ""
        slim.append(
            {
                "id": ev.get("id"),
                "summary": ev.get("summary"),
                "start": s,
                "status": ev.get("status"),
                "description_preview": (ev.get("description") or "")[:120].replace("\n", " "),
            }
        )
    print(json.dumps({"calendar_id": args.calendar_id, "events": slim}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
