#!/usr/bin/env python3
"""
Combine repo pulse + optional Google Calendar window + optional Kylo heartbeat files;
print a digest; optionally send Telegram; optionally append one line to a standing Calendar event.

Telegram inbound (asking what you ate / sleep times) is not implemented here — use a bot
+ webhook or long-poll worker next; this script is the outbound + calendar-write spine.

  pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib pyyaml

  python scripts/personal_ops_daily_digest.py --config config/personal_ops.example.yaml
  python scripts/personal_ops_daily_digest.py --config ... --telegram
  python scripts/personal_ops_daily_digest.py --config ... --stamp
  python scripts/personal_ops_daily_digest.py --config ... --stamp --append-event YOUR_EVENT_ID
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


def _load_config(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore

            return yaml.safe_load(text) or {}
        except ImportError as e:
            raise SystemExit("pip install pyyaml") from e
    return json.loads(text) or {}


def _heartbeat_snippet(path: Path) -> dict:
    out: dict = {"path": str(path), "exists": path.is_file()}
    if not path.is_file():
        return out
    out["mtime_utc"] = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            out["keys"] = sorted(data.keys())[:30]
            for k in ("ts", "timestamp", "updated_at", "last_ok", "status"):
                if k in data:
                    out[k] = data.get(k)
    except Exception as exc:
        out["parse_error"] = str(exc)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", type=Path, default=_root / "config" / "personal_ops.example.yaml")
    ap.add_argument("--telegram", action="store_true", help="Send digest via Telegram env vars.")
    ap.add_argument("--calendar-days", type=int, default=7, help="Include upcoming events for N days.")
    ap.add_argument("--stamp", action="store_true", help="Append one status line to the configured Calendar event.")
    ap.add_argument("--append-event", default="", help="Override event ID for --stamp (else calendar.progress_event_id).")
    args = ap.parse_args()

    cfg = _load_config(args.config)
    warn_days = float(cfg.get("stale_warning_days") or 7)

    from lib.repo_staleness import scan_repos

    repos_cfg = cfg.get("repos") or []
    pulses = scan_repos(repos_cfg if isinstance(repos_cfg, list) else [])

    lines: list[str] = []
    lines.append(f"AI-Lab ops digest {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")
    lines.append("")
    lines.append("Repos (git last commit):")
    stale_labels: list[str] = []
    for p in pulses:
        if p.error:
            lines.append(f"  - {p.label}: ERROR {p.error}")
            continue
        assert p.days_idle is not None
        flag = " **STALE**" if p.days_idle >= warn_days else ""
        lines.append(f"  - {p.label}: {p.days_idle} d idle (last {p.last_commit_iso}){flag}")
        if p.days_idle >= warn_days:
            stale_labels.append(p.label)

    hb_cfg = cfg.get("kylo_heartbeats") or []
    if isinstance(hb_cfg, list) and hb_cfg:
        lines.append("")
        lines.append("Kylo / worker pulses:")
        for item in hb_cfg:
            if isinstance(item, dict):
                raw = item.get("path")
            else:
                raw = str(item)
            if not raw:
                continue
            sn = _heartbeat_snippet(Path(str(raw)).expanduser())
            extra = sn.get("mtime_utc") or sn.get("parse_error") or sn.get("status") or ""
            lines.append(f"  - {sn['path']} exists={sn['exists']} {extra}".rstrip())

    cal_id = None
    cal_block = cfg.get("calendar") or {}
    if isinstance(cal_block, dict):
        cal_id = cal_block.get("calendar_id") or ("primary" if cal_block.get("primary") else None)

    events_slim: list[dict] = []
    if cal_id and args.calendar_days > 0:
        try:
            from lib.google_calendar_client import get_calendar_service, list_events

            svc = get_calendar_service()
            now = datetime.now(timezone.utc)
            end = now + timedelta(days=args.calendar_days)
            tfmt = "%Y-%m-%dT%H:%M:%SZ"
            raw_ev = list_events(
                svc,
                str(cal_id),
                time_min=now.strftime(tfmt),
                time_max=end.strftime(tfmt),
                max_results=80,
            )
            for ev in raw_ev:
                start = ev.get("start", {})
                s = start.get("dateTime") or start.get("date") or ""
                events_slim.append({"id": ev.get("id"), "summary": ev.get("summary"), "start": s})
            lines.append("")
            lines.append(f"Upcoming ({args.calendar_days}d, calendar={cal_id}):")
            for e in events_slim[:25]:
                lines.append(f"  - {e.get('start')} | {e.get('summary')}")
        except Exception as exc:
            lines.append("")
            lines.append(f"(Calendar skipped: {exc})")

    digest = "\n".join(lines)
    print(digest)

    event_id = (args.append_event or (cal_block.get("progress_event_id") if isinstance(cal_block, dict) else "") or "").strip()

    if args.stamp:
        if not event_id or not cal_id:
            print("--stamp requires calendar.calendar_id (or primary) and progress_event_id (or --append-event).", file=sys.stderr)
            return 1
        from lib.google_calendar_client import append_description_line, get_calendar_service

        stamp = f"[ops] stale={stale_labels or 'none'} at {datetime.now(timezone.utc).isoformat()}"
        svc = get_calendar_service()
        append_description_line(svc, str(cal_id), event_id, stamp)
        print(f"\nAppended line to calendar event {event_id}", file=sys.stderr)

    if args.telegram:
        from lib.telegram_simple import send_telegram_message, telegram_configured

        if not telegram_configured():
            print("Telegram env not set; skipped.", file=sys.stderr)
            return 1
        send_telegram_message(digest[:3900])
        print("Sent Telegram message.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
