"""
Company inbox cleaner: poll Gmail → rule triage → label + archive → log → toast.

Never deletes mail. Archive = remove system INBOX (and optionally UNREAD).
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_AI_LAB_ROOT = Path(__file__).resolve().parents[1]
if str(_AI_LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_LAB_ROOT))

from email_sorter.accounts import (  # noqa: E402
    AccountSpec,
    auth_check_all,
    load_account_specs,
    load_gmail_client_module,
    resolve_shared_credentials_file,
)
from email_sorter.company_triage import EmailMessage, classify_company_email  # noqa: E402

# Categories that should be highlighted in Acheron toasts
_ALERT_CATEGORIES = frozenset({"hot_urgent", "legal_compliance", "needs_review", "licenses_executive"})


def _extract_plain_body(payload: dict[str, Any]) -> str:
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
        if isinstance(part, dict) and (part.get("mimeType") or "").lower() == "text/plain":
            text = decode((part.get("body") or {}).get("data"))
            if text.strip():
                return text
    for part in payload.get("parts") or []:
        if isinstance(part, dict):
            nested = _extract_plain_body(part)
            if nested.strip():
                return nested
    return ""


def fetch_inbox_messages(service: Any, *, limit: int, unread_only: bool) -> list[dict[str, str]]:
    label_ids = ["INBOX", "UNREAD"] if unread_only else ["INBOX"]
    result = service.users().messages().list(
        userId="me",
        labelIds=label_ids,
        maxResults=max(1, min(limit, 100)),
    ).execute()
    out: list[dict[str, str]] = []
    for ref in result.get("messages") or []:
        message_id = ref.get("id")
        if not message_id:
            continue
        full = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        headers = {
            h.get("name", "").lower(): h.get("value", "")
            for h in (full.get("payload") or {}).get("headers") or []
        }
        out.append(
            {
                "id": message_id,
                "threadId": full.get("threadId", ""),
                "from": headers.get("from", ""),
                "subject": headers.get("subject", ""),
                "snippet": full.get("snippet", ""),
                "body": _extract_plain_body(full.get("payload") or {}),
            }
        )
    return out


def _log_path(run_id: str) -> Path:
    log_dir = _AI_LAB_ROOT / "logs" / "email_sorter"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"inbox_cleaner_{run_id}.jsonl"


def _append_log(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def process_account(
    account: AccountSpec,
    *,
    credentials_file: Path,
    limit: int,
    unread_only: bool,
    apply: bool,
    mark_read: bool,
    log_path: Path,
) -> list[dict[str, Any]]:
    gmail_client = load_gmail_client_module()
    gmail_client.clear_gmail_service_cache()
    if hasattr(gmail_client, "_LABEL_NAME_TO_ID"):
        gmail_client._LABEL_NAME_TO_ID.clear()  # type: ignore[attr-defined]

    service = gmail_client.get_gmail_service(
        token_file=str(account.token_file),
        credentials_file=str(credentials_file),
    )
    messages = fetch_inbox_messages(service, limit=limit, unread_only=unread_only)
    rows: list[dict[str, Any]] = []

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
        row: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "account_id": account.id,
            "account_email": account.email,
            "message_id": msg["id"],
            "thread_id": msg.get("threadId", ""),
            "from": msg.get("from", ""),
            "subject": msg.get("subject", ""),
            "snippet": (msg.get("snippet") or "")[:240],
            "triage": {
                "category": triage.category,
                "confidence": triage.confidence,
                "reasons": list(triage.reasons),
                "gmail_label": triage.gmail_label,
            },
            "applied": False,
            "archived": False,
            "dry_run": not apply,
            "alert": triage.category in _ALERT_CATEGORIES,
        }

        if apply:
            gmail_client.apply_label_and_archive(
                msg["id"],
                triage.gmail_label,
                mark_read=mark_read,
                token_file=str(account.token_file),
                credentials_file=str(credentials_file),
            )
            row["applied"] = True
            row["archived"] = True

        _append_log(log_path, row)
        rows.append(row)

    return rows


def build_deterministic_digest(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "Inbox clean - no messages processed."
    alerts = [r for r in rows if r.get("alert")]
    lines = [f"Cleaned {len(rows)} inbox message(s)."]
    if alerts:
        lines.append(f"Needs attention ({len(alerts)}):")
        for r in alerts[:8]:
            lines.append(
                f"• [{r['triage']['gmail_label']}] {r.get('subject') or '(no subject)'}"
            )
    else:
        by_label: dict[str, int] = {}
        for r in rows:
            lab = r["triage"]["gmail_label"]
            by_label[lab] = by_label.get(lab, 0) + 1
        summary = ", ".join(f"{k}×{v}" for k, v in sorted(by_label.items(), key=lambda x: -x[1]))
        lines.append(summary)
    return "\n".join(lines)


def run_cleaner(
    *,
    limit: int = 50,
    unread_only: bool = False,
    apply: bool = False,
    mark_read: bool = True,
    toast: bool = False,
    use_llm_summary: bool = True,
    llm_only_if_low_conf_or_alert: bool = True,
) -> dict[str, Any]:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    log_path = _log_path(run_id)
    credentials_file = resolve_shared_credentials_file()
    all_rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for account in load_account_specs():
        try:
            rows = process_account(
                account,
                credentials_file=credentials_file,
                limit=limit,
                unread_only=unread_only,
                apply=apply,
                mark_read=mark_read,
                log_path=log_path,
            )
            all_rows.extend(rows)
        except Exception as exc:
            errors.append({"account_id": account.id, "error": str(exc)})

    digest = build_deterministic_digest(all_rows)
    llm_summary: str | None = None
    need_llm = bool(all_rows) and use_llm_summary and (
        not llm_only_if_low_conf_or_alert
        or any(
            r.get("alert") or float((r.get("triage") or {}).get("confidence") or 1) < 0.75
            for r in all_rows
        )
    )
    if need_llm:
        try:
            from lib.ollama_simple import summarize_email_batch

            llm_summary = summarize_email_batch(all_rows)
            digest = llm_summary
        except Exception as exc:
            llm_summary = f"(ollama failed: {exc})"

    toast_result: dict[str, Any] | None = None
    if toast and all_rows:
        try:
            from lib.win_toast import notify_acheron_toast

            title = f"Email inbox cleaned ({len(all_rows)})"
            toast_result = notify_acheron_toast(title, digest)
        except Exception as exc:
            toast_result = {"ok": False, "error": str(exc)}

    return {
        "run_id": run_id,
        "log_path": str(log_path),
        "count": len(all_rows),
        "apply": apply,
        "errors": errors,
        "digest": digest,
        "llm_summary": llm_summary,
        "toast": toast_result,
        "rows": all_rows,
    }


def _cli() -> int:
    ap = argparse.ArgumentParser(description="Company Gmail inbox cleaner (label + archive).")
    ap.add_argument("--auth-check", action="store_true", help="Verify OAuth files for all accounts.")
    ap.add_argument("--limit", type=int, default=50, help="Max inbox messages per account.")
    ap.add_argument(
        "--unread-only",
        action="store_true",
        help="Only process UNREAD+INBOX (default: all INBOX).",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Apply labels and archive out of Inbox (default: dry-run).",
    )
    ap.add_argument(
        "--keep-unread",
        action="store_true",
        help="When applying, keep UNREAD (still remove INBOX).",
    )
    ap.add_argument("--toast", action="store_true", help="Send Acheron desktop toast summary.")
    ap.add_argument("--no-llm", action="store_true", help="Skip Ollama digest (deterministic text only).")
    ap.add_argument("--json", action="store_true", help="Print full JSON result.")
    ap.add_argument(
        "--loop-seconds",
        type=int,
        default=0,
        help="If >0, poll forever every N seconds (Ctrl+C to stop).",
    )
    args = ap.parse_args()

    if args.auth_check:
        report = auth_check_all()
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report.get("ok") else 1

    def once() -> int:
        result = run_cleaner(
            limit=args.limit,
            unread_only=args.unread_only,
            apply=args.apply,
            mark_read=not args.keep_unread,
            toast=args.toast,
            use_llm_summary=not args.no_llm,
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            mode = "APPLY" if args.apply else "DRY-RUN"
            print(f"[{mode}] processed={result['count']} log={result['log_path']}")
            if result["errors"]:
                print("errors:", json.dumps(result["errors"], ensure_ascii=False))
            print(result["digest"])
            if result.get("toast"):
                print("toast:", json.dumps(result["toast"], ensure_ascii=False))
        return 1 if result["errors"] and result["count"] == 0 else 0

    if args.loop_seconds and args.loop_seconds > 0:
        while True:
            once()
            time.sleep(args.loop_seconds)
    return once()


if __name__ == "__main__":
    raise SystemExit(_cli())
