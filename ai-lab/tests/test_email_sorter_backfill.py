from __future__ import annotations

import json
from pathlib import Path

import pytest

from email_sorter.backfill import (
    EmailRecord,
    _call_ai_classifier,
    _decide_label_actions,
    _deterministic_classify,
    _extract_json_object,
    _load_yaml,
)


AI_LAB_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = AI_LAB_ROOT / "email_sorter" / "config"


@pytest.fixture(scope="module")
def labels_cfg():
    return _load_yaml(CONFIG_DIR / "labels.yaml")


@pytest.fixture(scope="module")
def rules_cfg():
    return _load_yaml(CONFIG_DIR / "rules.yaml")


@pytest.fixture(scope="module")
def thresholds_cfg():
    return _load_yaml(CONFIG_DIR / "thresholds.yaml")


def _email(**kwargs) -> EmailRecord:
    return EmailRecord(
        message_id=kwargs.get("message_id", "m1"),
        thread_id=kwargs.get("thread_id"),
        from_header=kwargs.get("from_header", ""),
        sender_email=kwargs.get("sender_email", ""),
        sender_domain=kwargs.get("sender_domain", ""),
        subject=kwargs.get("subject", ""),
        snippet=kwargs.get("snippet", ""),
        body=kwargs.get("body", ""),
        attachment_filenames=kwargs.get("attachment_filenames", []),
        attachment_ids=kwargs.get("attachment_ids", []),
        attachment_mime_types=kwargs.get("attachment_mime_types", []),
        existing_label_names=kwargs.get("existing_label_names", []),
    )


def test_permit_keywords_alone_not_deterministic_permits(rules_cfg, thresholds_cfg):
    """Permits require AI/worker attachment content — not subject/body keywords alone."""
    email = _email(
        from_header="Dispatch <noreply@carrier.com>",
        sender_email="noreply@carrier.com",
        sender_domain="carrier.com",
        subject="Oversize Route Load Permit",
        body="Trailer details and Dimensions 12x8. Effective: 03/10/2026",
        attachment_filenames=[],
    )
    d = _deterministic_classify(email, rules=rules_cfg, thresholds=thresholds_cfg)
    assert d.category != "permits"


def test_pdf_filename_hint_not_deterministic_permits(rules_cfg, thresholds_cfg):
    email = _email(
        from_header="Unknown <someone@example.net>",
        sender_email="someone@example.net",
        sender_domain="example.net",
        subject="Route details",
        body="(no obvious permit keywords here)",
        attachment_filenames=["OVERSIZE_PERMIT_12345.pdf"],
        attachment_mime_types=["application/pdf"],
    )
    d = _deterministic_classify(email, rules=rules_cfg, thresholds=thresholds_cfg)
    assert d.category != "permits"


def test_pilotcarloads_goes_to_loads(rules_cfg, thresholds_cfg):
    email = _email(
        from_header="PilotCarLoads <team@pilotcarloads.com>",
        sender_email="team@pilotcarloads.com",
        sender_domain="pilotcarloads.com",
        subject="Load Alert #123",
        body="Dispatch details.",
        attachment_filenames=[],
    )
    d = _deterministic_classify(email, rules=rules_cfg, thresholds=thresholds_cfg)
    assert d.category == "loads"
    assert d.confidence >= float(thresholds_cfg["high"])


def test_mydot_email_deterministic(rules_cfg, thresholds_cfg):
    email = _email(
        from_header="MYDOT Notifications <no-reply@mydot.portal>",
        sender_email="no-reply@mydot.portal",
        sender_domain="mydot.portal",
        subject="MYDOT portal access granted",
        body="Your MYDOT account updated.",
    )
    d = _deterministic_classify(email, rules=rules_cfg, thresholds=thresholds_cfg)
    assert d.category == "mydot"
    assert d.confidence >= float(thresholds_cfg["high"])


def test_permit_body_only_without_attachment_or_alert_subject_skipped(rules_cfg, thresholds_cfg):
    """Permits require PDF/image or explicit load/permit subject — not body keywords alone."""
    email = _email(
        from_header="Someone <x@y.com>",
        sender_email="x@y.com",
        sender_domain="y.com",
        subject="Weekly operations update",
        body="dimensions 12x8 route trailer permit number effective issued",
        attachment_filenames=[],
    )
    d = _deterministic_classify(email, rules=rules_cfg, thresholds=thresholds_cfg)
    assert d.category != "permits"


def test_louisiana_mydotd_never_classified_as_permits(rules_cfg, thresholds_cfg):
    """LA DOT mydotd@info.la.gov = incident/road status, not client permits."""
    email = _email(
        from_header="MyDOTD <mydotd@info.la.gov>",
        sender_email="mydotd@info.la.gov",
        sender_domain="info.la.gov",
        subject="Road or Lane Status LANE CLOSURE: I-20 westbound at Nutland Rd",
        body="Traffic advisory with load and route wording in body text.",
        attachment_filenames=[],
    )
    d = _deterministic_classify(email, rules=rules_cfg, thresholds=thresholds_cfg)
    assert d.category == "mydot"
    assert d.category != "permits"
    assert d.confidence >= float(thresholds_cfg["high"])


def test_progressive_insurance_deterministic(rules_cfg, thresholds_cfg):
    email = _email(
        from_header="Progressive Insurance <alerts@progressive.com>",
        sender_email="alerts@progressive.com",
        sender_domain="progressive.com",
        subject="Progressive Commercial Insurance policy update",
        body="Policy premium and coverage details.",
    )
    d = _deterministic_classify(email, rules=rules_cfg, thresholds=thresholds_cfg)
    assert d.category == "progressive_insurance"
    assert d.confidence >= float(thresholds_cfg["medium"])


def test_driver_document_medium_confidence_no_child_label(labels_cfg, thresholds_cfg, rules_cfg):
    # No attachment filename includes a name => deterministic driver name likely None.
    email = _email(
        from_header="Dispatch <ops@carrier.com>",
        sender_email="ops@carrier.com",
        sender_domain="carrier.com",
        subject="Driver Credential - CDL qualification required",
        body="Qualification documents for driver credential and CDL license.",
        # Intentionally avoid credential keywords in the filename so deterministic
        # confidence stays in the medium band (no archive / no child label).
        attachment_filenames=["driver_documents.pdf"],
        attachment_mime_types=["application/pdf"],
    )
    d = _deterministic_classify(email, rules=rules_cfg, thresholds=thresholds_cfg)
    assert d.category == "driver_document"
    # Deterministic returns at least medium when any driver credential signals hit.
    assert d.confidence >= float(thresholds_cfg["medium"])

    proposed_labels, archive, child_label, would_create = _decide_label_actions(
        category=d.category,
        confidence=d.confidence,
        driver_name=d.driver_name,
        labels_cfg=labels_cfg,
        thresholds=thresholds_cfg,
        existing_driver_child_labels=set(),
    )
    assert archive is False
    assert labels_cfg["canonical"]["driver_parent"] in proposed_labels
    assert labels_cfg["canonical"]["needs_review"] in proposed_labels
    assert child_label is None
    assert would_create is False


def test_low_confidence_safety_needs_review_only(labels_cfg, thresholds_cfg, rules_cfg):
    email = _email(
        from_header="Someone <a@b.com>",
        sender_email="a@b.com",
        sender_domain="b.com",
        subject="Hello",
        body="Just saying hi.",
        attachment_filenames=["random.pdf"],
    )
    d = _deterministic_classify(email, rules=rules_cfg, thresholds=thresholds_cfg)
    assert d.category in {"uncategorized", "needs_review"}

    proposed_labels, archive, child_label, would_create = _decide_label_actions(
        category=d.category,
        confidence=d.confidence,
        driver_name=d.driver_name,
        labels_cfg=labels_cfg,
        thresholds=thresholds_cfg,
        existing_driver_child_labels=set(),
    )
    assert archive is False
    assert proposed_labels == [labels_cfg["canonical"]["needs_review"]]
    assert child_label is None
    assert would_create is False


def test_json_extraction_tolerates_trailing_text():
    reply = (
        'some text {"category":"permits","confidence":0.92,"reasons":["ok"],"driver_name":null,'
        '"should_create_driver_label":false,"suggested_labels":["Permits"]} \n\n_Used: permit_signals._'
    )
    obj = _extract_json_object(reply)
    assert obj is not None
    assert obj["category"] == "permits"
    assert float(obj["confidence"]) == 0.92


def test_ai_classifier_wrapper_parses_json(monkeypatch, rules_cfg, thresholds_cfg):
    # Patch orchestrator run to return an output that includes extra trailing text.
    from brain.orchestrator import main as orchestrator_main

    def fake_run(message: str, llm_base_url=None, llm_model=None, session_id="default"):
        return {
            "reply": (
                '{"category":"mydot","confidence":0.91,"reasons":["subject contains mydot"],'
                '"driver_name":null,"should_create_driver_label":false,"suggested_labels":["MYDOT"]} \n'
                "\n_Used: mydot_signals._"
            )
        }

    monkeypatch.setattr(orchestrator_main, "run", fake_run)

    email = _email(
        from_header="x <y@z.com>",
        sender_email="y@z.com",
        sender_domain="z.com",
        subject="MYDOT portal",
        body="",
        attachment_filenames=[],
    )
    deterministic = _deterministic_classify(email, rules=rules_cfg, thresholds=thresholds_cfg)

    cat, conf, reasons, driver_name, ai_used = _call_ai_classifier(
        email=email,
        deterministic=deterministic,
        thresholds=thresholds_cfg,
        config={"llm_base_url": "http://localhost:1234/v1", "llm_model": "test-model"},
    )

    assert ai_used is True
    assert cat == "mydot"
    assert conf == 0.91
    assert reasons
    assert driver_name is None

