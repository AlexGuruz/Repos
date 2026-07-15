from __future__ import annotations

from email_sorter.company_triage import EmailMessage, classify_company_email


def test_investor_subject_classifies():
    email = EmailMessage(
        account_id="jgdproperties",
        message_id="m1",
        thread_id="t1",
        from_header="Fund <fund@example.com>",
        subject="Updated term sheet for review",
        snippet="Please review the investment terms.",
        body="",
    )
    result = classify_company_email(email)
    assert result.category == "investors_finance"
    assert result.gmail_label == "Investors / Finance"


def test_retail_boost_for_nugz():
    email = EmailMessage(
        account_id="nugzdispo",
        message_id="m2",
        thread_id="t2",
        from_header="Vendor <orders@vendor.com>",
        subject="Inventory delivery update",
        snippet="Your retail inventory shipment is scheduled.",
        body="",
    )
    result = classify_company_email(email)
    assert result.category == "retail_operations"


def test_unknown_goes_to_needs_review():
    email = EmailMessage(
        account_id="jagadnursery",
        message_id="m3",
        thread_id="t3",
        from_header="Someone <x@example.com>",
        subject="Hello",
        snippet="Just checking in.",
        body="",
    )
    result = classify_company_email(email)
    assert result.category == "needs_review"
