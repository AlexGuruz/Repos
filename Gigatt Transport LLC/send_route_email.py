#!/usr/bin/env python3
"""
Send the Tom NY permit route email to gigatttransport3@gmail.com using
Gmail API and a Google service account (stashbox / sa.json).

Requires:
  - pip install google-auth google-auth-oauthlib google-api-python-client
  - Gmail API enabled on the project (ai-dataframe)
  - Domain-wide delegation for the service account to impersonate a Google
    Workspace user. Set that user's email in SEND_AS_EMAIL (env or below).

If you don't have Workspace: forward EMAIL-TO-GIGATTTRANSPORTLLC3.txt yourself.
"""
from __future__ import annotations

import base64
import os
from email.message import EmailMessage
from pathlib import Path

# Who receives the email
TO_EMAIL = "gigatttransport3@gmail.com"
SUBJECT = "Tom NY Permit 3841749 – GPS route links (Great Bend PA → 1070 Erie Ave North Tonawanda)"

BODY = r"""Tom NY Permit 3841749 – Exact GPS route

• Open this link on your phone or computer for turn-by-turn in Google Maps (tap "Start" for navigation):

https://www.google.com/maps/dir/?api=1&origin=41.97686,-75.74225&destination=43.04834,-78.85371&waypoints=42.0987%2C-75.918%7C42.2562%2C-77.9489%7C42.7959%2C-77.817%7C42.9784%2C-77.9372%7C43.0028%2C-78.2083%7C43.008%2C-78.235%7C42.9858%2C-78.3892%7C42.9006%2C-78.6392%7C42.9634%2C-78.7542%7C42.98018%2C-78.80534%7C42.9801%2C-78.8512%7C42.9962%2C-78.8776%7C43.0321%2C-78.8845&travelmode=driving

• Route: I-81 Great Bend, PA → NY-17 → I-86 → Exit 30 → NY-19 → NY-19A → NY-39 → NY-246 → NY-63 → Batavia Stafford Townline → NY-5 → NY-77 → NY-33 → NY-78 → NY-324 → I-290 → US-62 → NY-425 → 1070 Erie Ave, North Tonawanda NY 14120

• Exact GPX track and waypoint files (in repo): Tom-NY-permit-route-EXACT-TRACK.gpx and Tom-NY-permit-route-exact-waypoints.gpx
"""

# Service account path (stashbox)
SA_PATH = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS") or "E:/secrets/gcp/sa.json"
# Workspace user to send AS (must have domain-wide delegation for the service account)
SEND_AS_EMAIL = os.environ.get("SEND_AS_EMAIL", "").strip()


def main() -> None:
    if not SEND_AS_EMAIL:
        print("SEND_AS_EMAIL is not set. Gmail API with a service account requires")
        print("domain-wide delegation: you must send AS a Google Workspace user.")
        print("Set it and run again, e.g.:")
        print('  $env:SEND_AS_EMAIL = "you@yourworkspace.com"; python send_route_email.py')
        print("Or forward EMAIL-TO-GIGATTTRANSPORTLLC3.txt to gigatttransport3@gmail.com yourself.")
        return

    if not Path(SA_PATH).exists():
        print(f"Service account file not found: {SA_PATH}")
        return

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        SA_PATH,
        scopes=["https://www.googleapis.com/auth/gmail.send"],
    )
    delegated = creds.with_subject(SEND_AS_EMAIL)
    service = build("gmail", "v1", credentials=delegated)

    msg = EmailMessage()
    msg.set_content(BODY)
    msg["To"] = TO_EMAIL
    msg["From"] = SEND_AS_EMAIL
    msg["Subject"] = SUBJECT

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    try:
        service.users().messages().send(userId="me", body={"raw": raw}).execute()
        print(f"Sent to {TO_EMAIL} as {SEND_AS_EMAIL}.")
    except Exception as e:
        print("Send failed:", e)
        if "Precondition" in str(e) or "delegation" in str(e).lower():
            print("Ensure Gmail API is enabled and domain-wide delegation is set for this service account.")


if __name__ == "__main__":
    main()
