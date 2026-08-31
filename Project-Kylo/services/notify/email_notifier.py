"""Email notifiers for Kylo alerts.

Two transports, both exposing the same interface (``enabled``, ``missing()``,
``recipients``, ``send(subject, body) -> bool``) so callers never need to guard:

* ``EmailNotifier`` (SMTP) - modeled on ``syncthing_monitor/monitor.py``.
  Connection from env: SMTP_HOST, SMTP_PORT (587), SMTP_USERNAME, SMTP_PASSWORD,
  EMAIL_SENDER.
* ``GmailApiNotifier`` (Gmail API via a Google service account with domain-wide
  delegation) - "the stashbox service account". Sends as a delegated Workspace
  mailbox using ``gmail.send``; no SMTP creds needed.

``build_email_notifier`` selects the transport from ``notify.email.transport``
(``gmail_api`` or ``smtp``). If nothing is configured the notifier is a no-op
(``enabled`` False, ``send`` returns False).
"""
from __future__ import annotations

import base64
import os
import smtplib
from email.message import EmailMessage
from typing import Any, List, Optional, Sequence

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


def _split_csv(raw: str) -> List[str]:
    return [part.strip() for part in str(raw or "").split(",") if part.strip()]


def _dedupe(recipients: Optional[Sequence[str]]) -> List[str]:
    seen: set = set()
    out: List[str] = []
    for r in recipients or []:
        r = (r or "").strip()
        if r and r not in seen:
            seen.add(r)
            out.append(r)
    return out


class EmailNotifier:
    def __init__(
        self,
        *,
        host: str = "",
        port: int = 587,
        username: str = "",
        password: str = "",
        sender: str = "",
        recipients: Optional[Sequence[str]] = None,
    ) -> None:
        self.host = (host or "").strip()
        self.port = int(port or 587)
        self.username = (username or "").strip()
        self.password = (password or "").strip()
        self.sender = (sender or "").strip()
        self.recipients: List[str] = _dedupe(recipients)

    @property
    def enabled(self) -> bool:
        return bool(self.host and self.sender and self.recipients)

    def missing(self) -> List[str]:
        """Return the list of missing config pieces (for diagnostics)."""
        gaps = []
        if not self.host:
            gaps.append("SMTP_HOST")
        if not self.sender:
            gaps.append("EMAIL_SENDER")
        if not self.recipients:
            gaps.append("recipients")
        return gaps

    def send(self, subject: str, body: str) -> bool:
        """Send a plain-text email. Returns True on success, False otherwise."""
        if not self.enabled:
            return False
        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = self.sender
        message["To"] = ", ".join(self.recipients)
        message.set_content(body)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=15) as client:
                client.starttls()
                if self.username and self.password:
                    client.login(self.username, self.password)
                client.send_message(message)
            return True
        except Exception as exc:  # pragma: no cover - network failure path
            print(f"[EMAIL] send failed: {exc}")
            return False


class GmailApiNotifier:
    """Send mail via the Gmail API using a Google service account.

    The service account must have domain-wide delegation authorized for the
    ``gmail.send`` scope on the Workspace domain of ``sender``. The message is
    sent *as* ``sender`` (the impersonated/delegated mailbox).
    """

    def __init__(
        self,
        *,
        service_account_json: str = "",
        sender: str = "",
        recipients: Optional[Sequence[str]] = None,
    ) -> None:
        self.service_account_json = (service_account_json or "").strip()
        self.sender = (sender or "").strip()
        self.recipients: List[str] = _dedupe(recipients)

    @property
    def enabled(self) -> bool:
        return bool(
            self.service_account_json
            and os.path.exists(self.service_account_json)
            and self.sender
            and self.recipients
        )

    def missing(self) -> List[str]:
        gaps = []
        if not self.service_account_json or not os.path.exists(self.service_account_json):
            gaps.append("service_account_json")
        if not self.sender:
            gaps.append("sender")
        if not self.recipients:
            gaps.append("recipients")
        return gaps

    def send(self, subject: str, body: str) -> bool:
        if not self.enabled:
            return False
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build

            creds = service_account.Credentials.from_service_account_file(
                self.service_account_json, scopes=[GMAIL_SEND_SCOPE]
            ).with_subject(self.sender)
            svc = build("gmail", "v1", credentials=creds, cache_discovery=False)
            message = EmailMessage()
            message["Subject"] = subject
            message["From"] = self.sender
            message["To"] = ", ".join(self.recipients)
            message.set_content(body)
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
            svc.users().messages().send(userId="me", body={"raw": raw}).execute()
            return True
        except Exception as exc:  # pragma: no cover - network / auth path
            print(f"[EMAIL] gmail api send failed: {exc}")
            return False


def _collect_recipients(cfg: Any, extra_recipients: Optional[Sequence[str]]) -> List[str]:
    recipients: List[str] = []
    if extra_recipients:
        recipients.extend(extra_recipients)
    if cfg is not None and hasattr(cfg, "get"):
        try:
            cfg_recips = cfg.get("notify.email.recipients")
            if isinstance(cfg_recips, (list, tuple)):
                recipients.extend(str(x) for x in cfg_recips)
            elif isinstance(cfg_recips, str):
                recipients.extend(_split_csv(cfg_recips))
        except Exception:
            pass
    recipients.extend(_split_csv(os.environ.get("EMAIL_RECIPIENTS", "")))
    return _dedupe(recipients)


def _cfg_get(cfg: Any, dotted: str) -> Any:
    if cfg is not None and hasattr(cfg, "get"):
        try:
            return cfg.get(dotted)
        except Exception:
            return None
    return None


def build_email_notifier(
    cfg: Any = None,
    *,
    extra_recipients: Optional[Sequence[str]] = None,
):
    """Construct the configured email notifier (Gmail API or SMTP).

    Transport is chosen by ``notify.email.transport`` (default ``smtp``):
      * ``gmail_api`` -> ``GmailApiNotifier`` using the service account key at
        ``notify.email.service_account_json`` (fallback ``google.service_account_json_path``
        or env ``KYLO_GMAIL_SA_JSON`` / ``GOOGLE_APPLICATION_CREDENTIALS``), sending
        as ``notify.email.sender`` (fallback env ``EMAIL_SENDER``).
      * anything else -> SMTP ``EmailNotifier`` from env.

    Recipients merge (de-duplicated): ``extra_recipients`` + ``notify.email.recipients``
    + env ``EMAIL_RECIPIENTS``. If ``notify.email.enabled`` is explicitly False the
    notifier is disabled (no recipients).
    """
    enabled_val = _cfg_get(cfg, "notify.email.enabled")
    if enabled_val is False:
        return EmailNotifier()  # disabled no-op

    recipients = _collect_recipients(cfg, extra_recipients)
    transport = str(_cfg_get(cfg, "notify.email.transport") or "smtp").strip().lower()

    if transport == "gmail_api":
        sa_json = (
            str(_cfg_get(cfg, "notify.email.service_account_json") or "").strip()
            or str(_cfg_get(cfg, "google.service_account_json_path") or "").strip()
            or os.environ.get("KYLO_GMAIL_SA_JSON", "").strip()
            or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        )
        sender = (
            str(_cfg_get(cfg, "notify.email.sender") or "").strip()
            or os.environ.get("EMAIL_SENDER", "").strip()
        )
        return GmailApiNotifier(
            service_account_json=sa_json,
            sender=sender,
            recipients=recipients,
        )

    return EmailNotifier(
        host=os.environ.get("SMTP_HOST", ""),
        port=int(os.environ.get("SMTP_PORT", "587") or 587),
        username=os.environ.get("SMTP_USERNAME", ""),
        password=os.environ.get("SMTP_PASSWORD", ""),
        sender=os.environ.get("EMAIL_SENDER", ""),
        recipients=recipients,
    )


__all__ = ["EmailNotifier", "GmailApiNotifier", "build_email_notifier"]
