"""Unit tests for email notifier transport selection (no network)."""

from __future__ import annotations

from services.notify.email_notifier import (
    EmailNotifier,
    GmailApiNotifier,
    build_email_notifier,
)


class _Cfg:
    def __init__(self, data):
        self.data = data

    def get(self, dotted, default=None):
        cur = self.data
        for part in dotted.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                return default
        return cur


def test_gmail_transport_selected(tmp_path):
    sa = tmp_path / "sa.json"
    sa.write_text("{}")
    cfg = _Cfg(
        {
            "notify": {
                "email": {
                    "enabled": True,
                    "transport": "gmail_api",
                    "service_account_json": str(sa),
                    "sender": "alexstonedz@stonedprojects.com",
                    "recipients": ["alexstonedz@stonedprojects.com"],
                }
            }
        }
    )
    n = build_email_notifier(cfg)
    assert isinstance(n, GmailApiNotifier)
    assert n.enabled  # key file exists, sender + recipient present
    assert n.sender == "alexstonedz@stonedprojects.com"
    assert n.recipients == ["alexstonedz@stonedprojects.com"]


def test_gmail_missing_key_reports_gap():
    cfg = _Cfg(
        {
            "notify": {
                "email": {
                    "transport": "gmail_api",
                    "service_account_json": "E:/does/not/exist.json",
                    "sender": "a@b.com",
                    "recipients": ["a@b.com"],
                }
            }
        }
    )
    n = build_email_notifier(cfg)
    assert isinstance(n, GmailApiNotifier)
    assert not n.enabled
    assert "service_account_json" in n.missing()


def test_disabled_flag_makes_noop():
    cfg = _Cfg({"notify": {"email": {"enabled": False, "transport": "gmail_api"}}})
    n = build_email_notifier(cfg, extra_recipients=["x@y.com"])
    assert not n.enabled


def test_default_transport_is_smtp():
    cfg = _Cfg({"notify": {"email": {"recipients": ["a@b.com"]}}})
    n = build_email_notifier(cfg)
    assert isinstance(n, EmailNotifier)


def test_extra_recipients_merge_and_dedupe():
    cfg = _Cfg({"notify": {"email": {"recipients": ["a@b.com", "c@d.com"]}}})
    n = build_email_notifier(cfg, extra_recipients=["a@b.com", "z@z.com"])
    assert n.recipients == ["a@b.com", "z@z.com", "c@d.com"]
