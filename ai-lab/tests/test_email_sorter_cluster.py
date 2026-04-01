from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from email_sorter.cluster import (
    ClusterEmail,
    _cluster_emails,
    _propose_label_mapping_for_cluster,
    _load_labels_cfg,
    _generate_rules_patch_from_approved_mapping,
)


def test_cluster_emails_deterministic_merge():
    emails = [
        ClusterEmail(
            message_id="m1",
            sender="a@pilotcarloads.com",
            sender_domain="pilotcarloads.com",
            subject="PilotCarLoads Alert - Load Alert",
            snippet="",
            body="Route and dimensions for route load. Oversize permit issued.",
            attachment_filenames=[],
            attachment_mime_types=[],
            attachment_types=[],
        ),
        ClusterEmail(
            message_id="m2",
            sender="b@pilotcarloads.com",
            sender_domain="pilotcarloads.com",
            subject="PilotCarLoads Alert - Load Alert",
            snippet="",
            body="Route load dimensions. Effective date issued for oversize.",
            attachment_filenames=[],
            attachment_mime_types=[],
            attachment_types=[],
        ),
        ClusterEmail(
            message_id="m3",
            sender="c@other.com",
            sender_domain="other.com",
            subject="Hello there",
            snippet="",
            body="nothing to classify",
            attachment_filenames=[],
            attachment_mime_types=[],
            attachment_types=[],
        ),
    ]
    clusters = _cluster_emails(emails, merge_similarity=0.2)
    # Expect pilotcarloads emails in same cluster, and other.com separate.
    sizes = sorted([len(c) for c in clusters], reverse=True)
    assert sizes[0] == 2
    assert 1 in sizes


def test_label_suggestion_mydot():
    labels_cfg = _load_labels_cfg()
    cluster_name = "MYDOT Notifications"
    features = {
        "keywords": ["mydot", "dot", "incident", "crash"],
        "attachment_types": [],
    }
    suggested = _propose_label_mapping_for_cluster(cluster_name, features, labels_cfg)
    assert suggested["suggested_label"] == labels_cfg["canonical"]["mydot"]


def test_generate_rules_patch_skips_needs_review(tmp_path: Path):
    labels_cfg = _load_labels_cfg()

    # Minimal cluster_analysis structure.
    cluster_analysis = {
        "generated_at": "now",
        "clusters": [
            {
                "cluster_id": "cluster_001",
                "cluster_name": "Permit Documents",
                "count": 3,
                "features": {
                    "keywords": ["permit", "route", "dimensions"],
                    "attachment_patterns": [{"filename": "OVERSIZE_PERMIT_123.pdf", "count": 3}],
                    "attachment_types": [{"type": "pdf", "count": 3}],
                },
            },
            {
                "cluster_id": "cluster_002",
                "cluster_name": "General Inbox Cluster",
                "count": 2,
                "features": {"keywords": ["hello"], "attachment_patterns": [], "attachment_types": []},
            },
        ],
    }

    approved_mapping = {
        "clusters": {
            "cluster_001": {"approved_label": labels_cfg["canonical"]["permits"]},
            "cluster_002": {"approved_label": labels_cfg["canonical"]["needs_review"]},
        }
    }
    approved_path = tmp_path / "approved.yaml"
    approved_path.write_text(yaml.safe_dump(approved_mapping), encoding="utf-8")

    out_yaml = tmp_path / "rules_patch.yaml"
    _generate_rules_patch_from_approved_mapping(
        cluster_analysis=cluster_analysis,
        approved_mapping_path=approved_path,
        output_path=out_yaml,
        labels_cfg=labels_cfg,
    )

    patch = yaml.safe_load(out_yaml.read_text(encoding="utf-8"))
    additions = patch["rules_additions"]
    assert additions["permits"]["subject_keywords"]
    # Needs Review cluster should not add anything for other targets.
    assert not additions["mydot"]["subject_keywords"]
    assert not additions["progressive_insurance"]["subject_keywords"]
    assert not additions["driver_document"]["subject_keywords"]

