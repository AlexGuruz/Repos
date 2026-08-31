"""Lightweight tests for company inbox cleaner helpers (no live Gmail)."""
from __future__ import annotations

import ast
from pathlib import Path

from email_sorter.company_inbox_cleaner import build_deterministic_digest
from email_sorter.company_triage import EmailMessage, classify_company_email


def test_classify_fallback_needs_review():
    email = EmailMessage(
        account_id="nugzdispo",
        message_id="x",
        thread_id="t",
        from_header="Someone <random@example.com>",
        subject="Hello there",
        snippet="nothing special",
        body="nothing special",
    )
    triage = classify_company_email(email)
    assert triage.category == "needs_review"
    assert triage.gmail_label == "Needs Review"


def test_digest_flags_alerts():
    rows = [
        {
            "alert": True,
            "subject": "Urgent tax notice",
            "triage": {"gmail_label": "Hot / Urgent", "category": "hot_urgent", "confidence": 0.9},
        },
        {
            "alert": False,
            "subject": "Invoice",
            "triage": {"gmail_label": "Bills / Invoices", "category": "bills_invoices", "confidence": 0.9},
        },
    ]
    text = build_deterministic_digest(rows)
    assert "Cleaned 2" in text
    assert "Needs attention" in text
    assert "Urgent tax notice" in text


def test_archive_helpers_exist_in_portable_client():
    root = Path(__file__).resolve().parents[1]
    src = (root / "email_sorter" / "gmail_portable" / "app" / "gmail_client.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert "archive_message" in names
    assert "apply_label_and_archive" in names
    assert "removeLabelIds" in src and '"INBOX"' in src
