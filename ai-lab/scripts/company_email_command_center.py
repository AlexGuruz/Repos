#!/usr/bin/env python3
"""
Unified company inbox command center for multiple Gmail accounts.

Read path (auto-allowed):
  - fetch unread inbox mail
  - deterministic triage
  - print digest

Write/notify path (approval-gated):
  - Slack digest post
  - Gmail label apply
  - draft creation (future hook)

Setup:
  1) Put OAuth client JSON at secrets/gmail/credentials.json
  2) Auth each account:
       python -m email_sorter.accounts --auth jgdproperties
       python -m email_sorter.accounts --auth jagadnursery
       python -m email_sorter.accounts --auth nugzdispo
  3) Verify:
       python -m email_sorter.accounts --auth-check
  4) Digest:
       python scripts/company_email_command_center.py
  5) Slack (requires approval unless --approved):
       set SLACK_WEBHOOK_URL=...
       python scripts/company_email_command_center.py --slack --approved
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_root = Path(__file__).resolve().parents[1]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from email_sorter.accounts import auth_check_all, get_account_gmail_service, load_account_specs
from email_sorter.company_triage import EmailMessage, classify_company_email


def _fetch_unread_inbox(service: Any, *, limit: int) -> list[dict[str, str]]:
    result = service.users().messages().list(
        userId="me",
        labelIds=["INBOX", "UNREAD"],
        maxResults=max(1, min(limit, 100)),
    ).execute()
    messages = result.get("messages") or []
    out: list[dict[str, str]] = []
    for ref in messages:
        message_id = ref.get("id")
        if not message_id:
            continue
        full = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = {
            h.get("name", "").lower(): h.get("value", "")
            for h in (full.get("payload") or {}).get("headers") or []
        }
        body = _extract_plain_body(full.get("payload") or {})
        out.append(
            {
                "id": message_id,
                "threadId": full.get("threadId", ""),
                "from": headers.get("from", ""),
                "subject": headers.get("subject", ""),
                "snippet": full.get("snippet", ""),
                "body": body,
            }
        )
    return out


def _extract_plain_body(payload: dict[str, Any]) -> str:
    import base64

    def decode(data: str | None) -> str:
        if not data:
            return ""
        padded = data + "=" * (-len(data) % 4)
        return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8", errors="replace")

    mime = (payload.get("mimeType") or "").lower()
    body_data = (payload.get("body") or {}).get("data")
    if mime == "text/plain" and body_data:
        return decode(body_data)
    for part in payload.get("parts") or []:
        if not isinstance(part, dict):
            continue
        if (part.get("mimeType") or "").lower() == "text/plain":
            text = decode((part.get("body") or {}).get("data"))
            if text.strip():
                return text
    for part in payload.get("parts") or []:
        if isinstance(part, dict):
            nested = _extract_plain_body(part)
            if nested.strip():
                return nested
    return ""


def _build_digest(rows: list[dict[str, Any]]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [f"Company email digest — {now}", ""]
    if not rows:
        lines.append("No unread inbox messages matched the scan.")
        return "\n".join(lines)

    hot = [r for r in rows if r["triage"]["category"] == "hot_urgent"]
    if hot:
        lines.append("HOT / URGENT")
        for row in hot:
            lines.append(_format_row(row))
        lines.append("")

    by_account: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_account.setdefault(row["account_id"], []).append(row)

    for account_id, account_rows in by_account.items():
        lines.append(f"[{account_rows[0]['account_name']}] ({account_id})")
        for row in account_rows:
            if row["triage"]["category"] == "hot_urgent":
                continue
            lines.append(_format_row(row))
        lines.append("")

    return "\n".join(lines).rstrip()


def _format_row(row: dict[str, Any]) -> str:
    triage = row["triage"]
    label = triage["gmail_label"]
    conf = triage["confidence"]
    subject = row.get("subject") or "(no subject)"
    sender = row.get("from") or "(unknown sender)"
    return f"  - [{label} {conf:.2f}] {sender} | {subject}"


def _scan_accounts(*, per_account_limit: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for account in load_account_specs():
        try:
            service = get_account_gmail_service(account)
            messages = _fetch_unread_inbox(service, limit=per_account_limit)
        except Exception as exc:
            errors.append({"account_id": account.id, "error": str(exc)})
            continue
        for msg in messages:
            email = EmailMessage(
                account_id=account.id,
                message_id=msg["id"],
                thread_id=msg.get("threadId", ""),
                from_header=msg.get("from", ""),
                subject=msg.get("subject", ""),
                snippet=msg.get("snippet", ""),
                body=msg.get("body", ""),
            )
            triage = classify_company_email(email)
            rows.append(
                {
                    "account_id": account.id,
                    "account_name": account.display_name,
                    "account_email": account.email,
                    "message_id": msg["id"],
                    "thread_id": msg.get("threadId", ""),
                    "from": msg.get("from", ""),
                    "subject": msg.get("subject", ""),
                    "snippet": msg.get("snippet", ""),
                    "triage": {
                        "category": triage.category,
                        "confidence": triage.confidence,
                        "reasons": list(triage.reasons),
                        "gmail_label": triage.gmail_label,
                    },
                }
            )
    meta = {"errors": errors, "count": len(rows)}
    return rows, meta


def _queue_slack_approval(digest: str) -> str:
    from brain.approval_queue.queue import ApprovalSpec, submit

    preview = digest[:1200] + ("..." if len(digest) > 1200 else "")
    return submit(
        ApprovalSpec(
            file_path="scripts/company_email_command_center.py",
            action_type="notify",
            reason="Post company email digest to Slack",
            diff_preview=preview,
            risk_level="medium",
        )
    )


def _queue_label_actions(rows: list[dict[str, Any]], *, min_confidence: float) -> list[str]:
    from brain.approval_queue.queue import ApprovalSpec, submit

    approval_ids: list[str] = []
    for row in rows:
        triage = row["triage"]
        if triage["confidence"] < min_confidence:
            continue
        if triage["category"] == "needs_review":
            continue
        preview = (
            f"account={row['account_id']} message={row['message_id']}\n"
            f"label={triage['gmail_label']}\n"
            f"from={row.get('from','')}\n"
            f"subject={row.get('subject','')}"
        )
        approval_ids.append(
            submit(
                ApprovalSpec(
                    file_path=f"gmail:{row['account_id']}:{row['message_id']}",
                    action_type="modify",
                    reason=f"Apply Gmail label `{triage['gmail_label']}`",
                    diff_preview=preview,
                    risk_level="medium",
                )
            )
        )
    return approval_ids


def main() -> int:
    ap = argparse.ArgumentParser(description="Company email command center (multi-account Gmail).")
    ap.add_argument("--auth-check", action="store_true", help="Verify OAuth files for all configured accounts.")
    ap.add_argument("--limit", type=int, default=25, help="Max unread messages per account.")
    ap.add_argument("--slack", action="store_true", help="Send digest to Slack (approval-gated).")
    ap.add_argument("--queue-labels", action="store_true", help="Queue Gmail label actions for approval.")
    ap.add_argument("--min-confidence", type=float, default=0.85, help="Minimum confidence to queue label apply.")
    ap.add_argument("--approved", action="store_true", help="Bypass approval gate for gated actions in this run.")
    ap.add_argument("--json", action="store_true", help="Print structured JSON instead of digest text.")
    args = ap.parse_args()

    if args.auth_check:
        report = auth_check_all()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("ok") else 1

    rows, meta = _scan_accounts(per_account_limit=args.limit)
    digest = _build_digest(rows)

    if args.json:
        print(json.dumps({"rows": rows, "meta": meta, "digest": digest}, ensure_ascii=False, indent=2))
    else:
        print(digest)
        if meta["errors"]:
            print("\nErrors:", file=sys.stderr)
            for err in meta["errors"]:
                print(f"  - {err['account_id']}: {err['error']}", file=sys.stderr)

    from brain.orchestrator.approval_gate import requires_approval

    if args.slack:
        if requires_approval("notify") and not args.approved:
            approval_id = _queue_slack_approval(digest)
            print(f"\nSlack notify queued for approval: {approval_id}", file=sys.stderr)
        else:
            from lib.slack_simple import send_slack_message, slack_configured

            if not slack_configured():
                print("SLACK_WEBHOOK_URL not set; skipped Slack send.", file=sys.stderr)
                return 1
            send_slack_message(digest[:3900])
            print("\nSent Slack digest.", file=sys.stderr)

    if args.queue_labels:
        if requires_approval("modify") and not args.approved:
            ids = _queue_label_actions(rows, min_confidence=args.min_confidence)
            if ids:
                print(f"\nQueued {len(ids)} label action(s) for approval.", file=sys.stderr)
                for approval_id in ids:
                    print(f"  - {approval_id}", file=sys.stderr)
            else:
                print("\nNo label actions met the confidence threshold.", file=sys.stderr)
        else:
            print("\nLabel apply execution is not enabled in this script yet; use approval queue + manual apply.", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
