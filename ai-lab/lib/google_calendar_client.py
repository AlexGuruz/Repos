"""
Google Calendar API helper (separate OAuth token from Gmail).

Uses the same OAuth *client* file as the bundled Gmail adapter
(`GOOGLE_CREDENTIALS_FILE` or `email_sorter/gmail_portable/credentials.json`),
but defaults to a dedicated token file so adding Calendar scopes does not
invalidate your existing Gmail token.json.

Env:
  GOOGLE_CREDENTIALS_FILE — OAuth client JSON (installed app).
  GOOGLE_CALENDAR_TOKEN_FILE — token path for Calendar (default: sibling
      `token.calendar.json` next to credentials, else gmail_portable/token.calendar.json).
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import Resource, build
from google_auth_oauthlib.flow import InstalledAppFlow

LOGGER = logging.getLogger(__name__)

# calendar.events: create/update/delete events. calendar.readonly: calendarList (multi-calendar).
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
]

_ADAPTER_ROOT = Path(__file__).resolve().parents[1] / "email_sorter" / "gmail_portable"
_LEGACY_CREDENTIALS_FILE = _ADAPTER_ROOT / "credentials.json"
_LEGACY_TOKEN_FILE = _ADAPTER_ROOT / "token.calendar.json"


def _resolve_env_path(value: str | None) -> Path | None:
    raw = (value or "").strip()
    if not raw:
        return None
    p = Path(raw)
    if not p.is_absolute():
        p = _ADAPTER_ROOT / p
    return p


def _credentials_path() -> Path | None:
    for p in (
        _resolve_env_path(os.getenv("GOOGLE_CREDENTIALS_FILE")),
        _LEGACY_CREDENTIALS_FILE,
    ):
        if p and p.is_file():
            return p
    return None


def _calendar_token_path(credentials_file: Path) -> Path:
    env = _resolve_env_path(os.getenv("GOOGLE_CALENDAR_TOKEN_FILE"))
    if env:
        return env
    return credentials_file.parent / "token.calendar.json"


def preflight_calendar_auth() -> dict[str, Any]:
    cred = _credentials_path()
    tok = _calendar_token_path(cred) if cred else _LEGACY_TOKEN_FILE
    return {
        "ok": bool(cred and cred.is_file()) or tok.is_file(),
        "credentials_file": str(cred) if cred else None,
        "calendar_token_file": str(tok),
        "token_exists": tok.is_file(),
    }


def get_calendar_service() -> Resource:
    credentials_file = _credentials_path()
    if not credentials_file:
        raise FileNotFoundError(
            "No Google OAuth client secrets found. Set GOOGLE_CREDENTIALS_FILE or place "
            f"credentials.json at {_LEGACY_CREDENTIALS_FILE}"
        )
    token_file = _calendar_token_path(credentials_file)
    creds: Credentials | None = None
    if token_file.is_file():
        try:
            creds = Credentials.from_authorized_user_file(str(token_file), CALENDAR_SCOPES)
        except Exception:
            LOGGER.warning("Invalid calendar token; re-auth required: %s", token_file)
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            with credentials_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict) or not (data.get("installed") or data.get("web")):
                raise ValueError("credentials.json must use OAuth 'installed' or 'web' client format.")
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_file), CALENDAR_SCOPES)
            creds = flow.run_local_server(port=0)
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json(), encoding="utf-8")

    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def list_calendars(service: Resource) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    page_token = None
    while True:
        resp = service.calendarList().list(pageToken=page_token).execute()
        for item in resp.get("items", []):
            out.append(
                {
                    "id": item.get("id"),
                    "summary": item.get("summary"),
                    "primary": item.get("primary", False),
                    "timeZone": item.get("timeZone"),
                    "accessRole": item.get("accessRole"),
                }
            )
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return out


def list_events(
    service: Resource,
    calendar_id: str,
    *,
    time_min: str,
    time_max: str,
    max_results: int = 250,
) -> list[dict[str, Any]]:
    """time_min/time_max in RFC3339 (e.g. Zulu)."""
    out: list[dict[str, Any]] = []
    page_token = None
    while True:
        resp = (
            service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy="startTime",
                maxResults=min(250, max_results - len(out)),
                pageToken=page_token,
            )
            .execute()
        )
        out.extend(resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token or len(out) >= max_results:
            break
    return out[:max_results]


def append_description_line(
    service: Resource,
    calendar_id: str,
    event_id: str,
    line: str,
    *,
    separator: str = "\n\n— AI-Lab ops —\n",
) -> dict[str, Any]:
    """
    Fetch event, append `line` to description (creates description if empty).
    Returns updated event resource.
    """
    ev = service.events().get(calendarId=calendar_id, eventId=event_id).execute()
    desc = (ev.get("description") or "").rstrip()
    add = f"{separator}{line.strip()}" if desc else line.strip()
    new_desc = desc + add
    ev["description"] = new_desc
    return service.events().update(calendarId=calendar_id, eventId=event_id, body=ev).execute()


def create_text_event(
    service: Resource,
    calendar_id: str,
    *,
    summary: str,
    description: str,
    start_rfc3339: str,
    end_rfc3339: str,
    time_zone: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_rfc3339, "timeZone": time_zone or "UTC"},
        "end": {"dateTime": end_rfc3339, "timeZone": time_zone or "UTC"},
    }
    return service.events().insert(calendarId=calendar_id, body=body).execute()
