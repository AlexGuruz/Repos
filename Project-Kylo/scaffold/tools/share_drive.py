from __future__ import annotations

import argparse
import json
import os
import sys

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build


def get_drive_service(creds_path: str):
    scopes = [
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    return build("drive", "v3", credentials=creds)


def share_file(file_id: str, email: str, role: str = "writer", send_notification: bool = False) -> dict:
    creds_path = os.environ.get(
        "GOOGLE_APPLICATION_CREDENTIALS",
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "secrets", "service_account.json"),
    )
    service = get_drive_service(creds_path)
    body = {"type": "user", "role": role, "emailAddress": email}
    return (
        service.permissions()
        .create(fileId=file_id, body=body, sendNotificationEmail=send_notification)
        .execute()
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Share a Drive file with a user via service account")
    p.add_argument("--file-id", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--role", default="writer", choices=["reader", "commenter", "writer", "owner"])  # owner requires transfer
    p.add_argument("--notify", action="store_true", help="Send notification email")
    args = p.parse_args()

    try:
        res = share_file(args.file_id, args.email, role=args.role, send_notification=args.notify)
        print(json.dumps(res))
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


