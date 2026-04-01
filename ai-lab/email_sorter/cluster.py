from __future__ import annotations

import argparse
import base64
import imaplib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any, Iterable

import yaml


_REPO_ROOT = Path(__file__).resolve().parents[1]
_CONFIG_DIR = Path(__file__).resolve().parent / "config"


ALLOWED_CLUSTER_LABELS = {
    "Permits",
    "MYDOT",
    "PROGRESSIVE COMMERCIAL INSURANCE",
    "Driver Credentials / Documents",
    "Needs Review",
}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _imap_secret_load(secret_file: Path) -> tuple[str, str]:
    """
    Expected format based on `E:/secrets/gigatt imap.txt`:
      line1: password (may contain spaces; spaces are removed)
      line2: mailbox address
    """
    raw = secret_file.read_text(encoding="utf-8").splitlines()
    lines = [l.strip() for l in raw if l.strip()]
    if len(lines) < 2:
        raise ValueError(f"IMAP secret file must contain at least 2 non-empty lines: {secret_file}")
    pwd_raw = lines[0].replace(" ", "")
    username = lines[1]
    return username, pwd_raw


def _parse_email_sender(from_header: str) -> tuple[str, str]:
    """
    Returns (sender_email, sender_domain)
    """
    if not from_header:
        return "", ""
    # Handles: "Name <email@domain.com>"
    m = re.search(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", from_header, flags=re.I)
    addr = m.group(1).strip().lower() if m else from_header.strip().lower()
    domain = addr.split("@", 1)[1].strip().lower() if "@" in addr else ""
    return addr, domain


def _normalize_ws(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _strip_html(html: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z0-9]+", (text or "").lower())
    # Lightweight stoplist to reduce noisy tokens.
    stop = {
        "the",
        "and",
        "or",
        "to",
        "of",
        "in",
        "for",
        "a",
        "an",
        "your",
        "you",
        "with",
        "from",
        "subject",
        "re",
        "fw",
        "fwd",
        "http",
        "https",
    }
    return [t for t in tokens if t not in stop and len(t) >= 3]


def _attachment_type_summary(attachment_filenames: list[str], attachment_mime_types: list[str]) -> list[str]:
    types: set[str] = set()
    for fn, mt in zip(attachment_filenames or [], attachment_mime_types or []):
        fn_l = (fn or "").lower()
        mt_l = (mt or "").lower()
        if mt_l == "application/pdf" or fn_l.endswith(".pdf"):
            types.add("pdf")
        elif mt_l.startswith("image/") or any(fn_l.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"]):
            types.add("image")
        elif mt_l:
            types.add(mt_l.split("/", 1)[0])
        else:
            types.add("other")
    return sorted(types)


@dataclass
class ClusterEmail:
    message_id: str
    sender: str
    sender_domain: str
    subject: str
    snippet: str
    body: str
    attachment_filenames: list[str]
    attachment_mime_types: list[str]
    attachment_types: list[str]


def _imap_parse_email(raw: bytes, *, fallback_imap_seq: str) -> ClusterEmail:
    """
    Parse raw RFC822 bytes into a lightweight feature representation.
    """
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    from_header = msg.get("From", "") or ""
    subject = msg.get("Subject", "") or ""

    message_id_header = msg.get("Message-ID", "") or ""
    message_id_header = message_id_header.strip().strip("<>").strip()
    message_id = message_id_header or fallback_imap_seq

    sender_email, sender_domain = _parse_email_sender(from_header)

    # For speed: we only need a representative body sample for similarity,
    # not the entire message.
    plain_text: str = ""
    html_text: str = ""
    max_body_chars = int(os.environ.get("EMAIL_SORTER_CLUSTER_MAX_BODY_CHARS", "8000"))
    attachment_filenames: list[str] = []
    attachment_mime_types: list[str] = []
    max_attachments = int(os.environ.get("EMAIL_SORTER_CLUSTER_MAX_ATTACHMENTS", "6"))

    # Walk message and keep:
    # - text payloads for lightweight similarity
    # - attachment metadata (filename + mime type)
    for part in msg.walk():
        if part.is_multipart():
            continue

        disp = (part.get_content_disposition() or "").lower()
        ctype = (part.get_content_type() or "").lower()
        filename = (part.get_filename() or "").strip()

        # Attachments are sometimes marked as `attachment` with/without filename.
        if disp == "attachment" or (filename and disp in {"", "inline"}):
            # Keep filename if available; still record mime type for attachment-type clustering.
            if len(attachment_filenames) < max_attachments:
                if filename:
                    attachment_filenames.append(filename)
                else:
                    attachment_filenames.append("")
                attachment_mime_types.append(ctype)
            continue

        if ctype == "text/plain" and disp != "attachment" and not plain_text:
            payload = part.get_payload(decode=True) or b""
            try:
                plain_text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            except Exception:
                plain_text = payload.decode("utf-8", errors="replace")
        elif ctype == "text/html" and disp != "attachment" and not html_text:
            payload = part.get_payload(decode=True) or b""
            try:
                html_text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            except Exception:
                html_text = payload.decode("utf-8", errors="replace")

    if plain_text:
        body_text = _normalize_ws(plain_text)[:max_body_chars]
    elif html_text:
        body_text = _normalize_ws(_strip_html(html_text))[:max_body_chars]
    else:
        body_text = ""

    snippet = (body_text[:200] if body_text else "").strip()
    attachment_types = _attachment_type_summary(attachment_filenames, attachment_mime_types)

    return ClusterEmail(
        message_id=message_id,
        sender=sender_email or from_header,
        sender_domain=sender_domain,
        subject=subject,
        snippet=snippet,
        body=body_text,
        attachment_filenames=attachment_filenames,
        attachment_mime_types=attachment_mime_types,
        attachment_types=attachment_types,
    )


def _imap_scan_last_n_emails(
    *,
    imap_secret_file: str,
    imap_host: str,
    imap_port: int,
    limit: int,
    imap_timeout_sec: int,
    fetch_retries: int,
) -> tuple[list[ClusterEmail], dict[str, Any]]:
    secret_path = Path(imap_secret_file)
    username, password = _imap_secret_load(secret_path)

    imap = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=imap_timeout_sec)
    imap.login(username, password)
    imap.select("INBOX")

    # Deterministic: fetch ALL ids, then take last `limit`.
    # Note: Phase 1 requires 200-500; this is acceptable for an offline analysis run.
    typ, data = imap.search(None, "ALL")
    ids: list[int] = []
    if isinstance(data, list) and data and data[0]:
        ids = [int(x) for x in data[0].split() if x]
    ids = sorted(ids)[-max(1, limit):]

    emails: list[ClusterEmail] = []
    fetched_count = 0
    failed_count = 0
    try:
        for seq_id in ids:
            raw = b""
            last_err: str | None = None
            for attempt in range(1, max(1, fetch_retries) + 1):
                try:
                    typ2, fetched = imap.fetch(str(seq_id), "(RFC822)")
                    if isinstance(fetched, list):
                        for part in fetched:
                            if isinstance(part, tuple) and part[1]:
                                raw = part[1]
                                break
                    break
                except Exception as e:
                    last_err = f"{type(e).__name__}: {e}"
                    time.sleep(0.5 * attempt)

            if not raw:
                failed_count += 1
                continue

            fetched_count += 1
            emails.append(_imap_parse_email(raw, fallback_imap_seq=f"imap-{seq_id}"))
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    meta = {"fetched_count": fetched_count, "failed_count": failed_count, "requested_limit": limit}
    return emails, meta


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a.intersection(b))
    union = len(a.union(b))
    return inter / union if union else 0.0


def _feature_signature(email: ClusterEmail) -> tuple[str, str]:
    """
    Deterministic coarse signature used to create initial clusters.
    """
    domain = email.sender_domain or "unknown_domain"
    atts = ",".join(email.attachment_types) if email.attachment_types else "no_attachments"
    return domain, atts


def _cluster_emails(emails: list[ClusterEmail], *, merge_similarity: float = 0.35) -> list[list[ClusterEmail]]:
    """
    Deterministic clustering:
    1) seed groups by (sender_domain, attachment_types_signature)
    2) within each seed group, merge near-duplicate subjects/bodies using Jaccard similarity.
    """
    seed: dict[tuple[str, str], list[ClusterEmail]] = defaultdict(list)
    for e in emails:
        seed[_feature_signature(e)].append(e)

    clusters: list[list[ClusterEmail]] = []
    for _, seed_emails in seed.items():
        # Sort to keep determinism: by sender then subject.
        seed_emails = sorted(seed_emails, key=lambda x: (x.sender_domain, x.subject or "", x.message_id))

        # Maintain cluster representatives by token sets.
        reps: list[set[str]] = []
        cluster_lists: list[list[ClusterEmail]] = []

        for e in seed_emails:
            subj_tokens = set(_tokenize(e.subject))
            body_tokens = set(_tokenize(e.body[:8000]))
            # Similarity across subject+body.
            tokens = subj_tokens.union(body_tokens)

            placed = False
            for i, rep in enumerate(reps):
                if _jaccard(tokens, rep) >= merge_similarity:
                    cluster_lists[i].append(e)
                    # Update rep as union of top tokens.
                    reps[i] = rep.union(tokens)
                    placed = True
                    break
            if not placed:
                reps.append(tokens)
                cluster_lists.append([e])

        clusters.extend(cluster_lists)

    # Final determinism: sort clusters by size desc, then stable key.
    def cluster_sort_key(c: list[ClusterEmail]) -> tuple[int, str]:
        dom = c[0].sender_domain or ""
        subj = c[0].subject or ""
        return (-len(c), dom, subj)

    clusters = sorted(clusters, key=cluster_sort_key)
    return clusters


def _suggest_cluster_name(email_cluster: list[ClusterEmail]) -> str:
    all_text = "\n".join([e.subject + "\n" + (e.body[:4000] or "") for e in email_cluster])
    tokens = Counter(_tokenize(all_text))
    top = [t for t, _ in tokens.most_common(10)]
    atts = sorted({t for e in email_cluster for t in e.attachment_types})
    top_str = " ".join(top)

    if any(t in top_str for t in ["permit", "oversize", "route", "dimensions", "load", "trailer"]):
        return "Permit Documents"
    if any(t in top_str for t in ["mydot", "my", "dot"]):
        return "MYDOT Notifications"
    if any(t in top_str for t in ["progressive", "insurance", "policy", "premium", "commercial"]):
        return "Progressive Insurance"
    if any(t in top_str for t in ["driver", "cdl", "license", "credential", "credentials", "qualification", "mvr"]):
        return "Driver Credentials / Documents"
    if any(t in top_str for t in ["statement", "balance", "routing", "payment"]):
        return "Billing / Statements"

    # Attachment-driven fallback.
    if "pdf" in atts and len(email_cluster) <= 10:
        return "Document Inbox (PDF)"
    if "image" in atts and len(email_cluster) <= 10:
        return "Scanned Document (Images)"
    return "General Inbox Cluster"


def _cluster_features(email_cluster: list[ClusterEmail]) -> dict[str, Any]:
    senders = Counter(e.sender for e in email_cluster)
    domains = Counter(e.sender_domain for e in email_cluster if e.sender_domain)
    subject_tokens = Counter(_tokenize(" ".join([e.subject for e in email_cluster])))
    body_tokens = Counter(_tokenize(" ".join([e.body[:8000] for e in email_cluster])))
    attachment_types = Counter(t for e in email_cluster for t in e.attachment_types)
    filenames = Counter(fn for e in email_cluster for fn in (e.attachment_filenames or []))

    # Merge keyword evidence: prefer subject tokens, then body.
    keywords = [t for t, _ in subject_tokens.most_common(8)]
    if len(keywords) < 8:
        keywords.extend([t for t, _ in body_tokens.most_common(8 - len(keywords))])
    keywords = keywords[:8]

    attachment_patterns = []
    for fn, cnt in filenames.most_common(6):
        if not fn:
            continue
        attachment_patterns.append({"filename": fn, "count": cnt})

    return {
        "senders_top": [{"sender": s, "count": c} for s, c in senders.most_common(5)],
        "domains_top": [{"domain": d, "count": c} for d, c in domains.most_common(5)],
        "keywords": keywords,
        "attachment_types": [{"type": t, "count": c} for t, c in attachment_types.most_common(5)],
        "attachment_patterns": attachment_patterns,
    }


def _load_labels_cfg() -> dict[str, Any]:
    return _load_yaml(_CONFIG_DIR / "labels.yaml")


def _propose_label_mapping_for_cluster(cluster_name: str, features: dict[str, Any], labels_cfg: dict[str, Any]) -> dict[str, Any]:
    canonical = labels_cfg.get("canonical") or {}
    permits = canonical.get("permits", "Permits")
    mydot = canonical.get("mydot", "MYDOT")
    progressive = canonical.get("progressive_insurance", "PROGRESSIVE COMMERCIAL INSURANCE")
    driver_parent = canonical.get("driver_parent", "Driver Credentials / Documents")
    needs_review = canonical.get("needs_review", "Needs Review")

    # Deterministic mapping first.
    name_l = (cluster_name or "").lower()
    keywords = [k.lower() for k in (features.get("keywords") or [])]
    kw_set = set(keywords)
    type_set = {t["type"] for t in features.get("attachment_types") or []}

    if "permit" in name_l or kw_set.intersection({"permit", "oversize", "route", "dimensions", "load", "trailer"}):
        return {"cluster_name": cluster_name, "suggested_label": permits, "confidence": 0.9, "rationale": ["permit_signals"]}
    if "mydot" in name_l or kw_set.intersection({"mydot", "dot"}):
        return {"cluster_name": cluster_name, "suggested_label": mydot, "confidence": 0.85, "rationale": ["mydot_signals"]}
    if "progressive" in name_l or kw_set.intersection({"progressive", "insurance", "policy", "premium", "commercial"}):
        return {"cluster_name": cluster_name, "suggested_label": progressive, "confidence": 0.8, "rationale": ["progressive_signals"]}
    if "driver" in name_l or kw_set.intersection({"driver", "cdl", "license", "credential", "credentials", "qualification", "mvr"}):
        return {"cluster_name": cluster_name, "suggested_label": driver_parent, "confidence": 0.82, "rationale": ["driver_signals"]}
    if kw_set.intersection({"statement", "balance", "routing", "payment"}):
        # Per your Phase 1 safety guidance: conservative -> Needs Review.
        return {"cluster_name": cluster_name, "suggested_label": needs_review, "confidence": 0.45, "rationale": ["bank_or_billing_signals_to_needs_review"]}
    if "pdf" in type_set or "image" in type_set:
        return {"cluster_name": cluster_name, "suggested_label": needs_review, "confidence": 0.55, "rationale": ["document_uncertain_to_needs_review"]}
    return {"cluster_name": cluster_name, "suggested_label": needs_review, "confidence": 0.5, "rationale": ["default_uncertain"]}


def _write_cluster_analysis_md(*, clusters: list[list[ClusterEmail]], output_path: Path) -> None:
    labels_cfg = _load_labels_cfg()
    lines: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    lines.append("# Email Cluster Analysis (Discovery Only)")
    lines.append("")
    lines.append(f"- Generated at: `{now}`")
    lines.append(f"- Cluster count: `{len(clusters)}`")
    lines.append("")

    for idx, c in enumerate(clusters, start=1):
        cluster_name = _suggest_cluster_name(c)
        features = _cluster_features(c)
        suggested = _propose_label_mapping_for_cluster(cluster_name, features, labels_cfg)

        lines.append(f"## Cluster {idx}")
        lines.append("")
        lines.append(f"Name suggestion: **{cluster_name}**")
        lines.append(f"Count: `{len(c)}`")
        lines.append("")
        lines.append("Key features:")
        lines.append("")
        lines.append(f"- Senders/domains: `{(features.get('domains_top') or features.get('senders_top'))[:3]}`")
        lines.append(f"- Keywords: `{', '.join(features.get('keywords') or [])}`")
        att_types = [x["type"] for x in (features.get("attachment_types") or [])]
        lines.append(f"- Attachment types: `{', '.join(att_types) if att_types else 'none'}`")
        lines.append("")
        if features.get("attachment_patterns"):
            lines.append("Attachment patterns:")
            lines.append("")
            for p in features["attachment_patterns"][:5]:
                lines.append(f"- `{p['filename']}` (x{p['count']})")
            lines.append("")

        # Label suggestion (proposal only; no auto-create in this phase).
        lines.append("Label suggestion (proposal only):")
        lines.append("")
        lines.append(f"- Suggested label: **{suggested['suggested_label']}**")
        lines.append(f"- Confidence: `{suggested['confidence']}`")
        lines.append(f"- Rationale: `{', '.join(suggested.get('rationale') or [])}`")
        lines.append("")

        lines.append("Sample emails:")
        lines.append("")
        for e in c[:5]:
            snippet = (e.snippet or "").replace("\n", " ")[:120]
            lines.append(f"- `{e.message_id}` | {e.sender_domain or e.sender} | {e.subject[:80]}")
            if snippet:
                lines.append(f"  Body snippet: {snippet}")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_cluster_analysis_json(*, clusters: list[list[ClusterEmail]], output_path: Path) -> None:
    output: dict[str, Any] = {"generated_at": datetime.now(timezone.utc).isoformat(), "clusters": []}
    for idx, c in enumerate(clusters, start=1):
        cluster_name = _suggest_cluster_name(c)
        features = _cluster_features(c)
        output["clusters"].append(
            {
                "cluster_id": f"cluster_{idx:03d}",
                "cluster_name": cluster_name,
                "count": len(c),
                "features": features,
                "emails_sample": [
                    {
                        "message_id": e.message_id,
                        "sender": e.sender,
                        "sender_domain": e.sender_domain,
                        "subject": e.subject,
                        "snippet": e.snippet,
                        "attachment_types": e.attachment_types,
                        "attachment_filenames": e.attachment_filenames[:3],
                    }
                    for e in c[:5]
                ],
            }
        )

    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")


def _load_cluster_analysis_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"cluster_analysis.json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _write_label_suggestions_md(*, cluster_analysis: dict[str, Any], output_path: Path, labels_cfg: dict[str, Any]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    lines: list[str] = []
    lines.append("# Cluster Label Suggestions (Proposal Only)")
    lines.append("")
    lines.append(f"- Generated at: `{now}`")
    lines.append("")

    canonical = labels_cfg.get("canonical") or {}
    label_names = {
        "permits": canonical.get("permits", "Permits"),
        "mydot": canonical.get("mydot", "MYDOT"),
        "progressive_insurance": canonical.get("progressive_insurance", "PROGRESSIVE COMMERCIAL INSURANCE"),
        "driver_document": canonical.get("driver_parent", "Driver Credentials / Documents"),
        "needs_review": canonical.get("needs_review", "Needs Review"),
    }

    for c in cluster_analysis.get("clusters") or []:
        cluster_id = c.get("cluster_id") or ""
        cluster_name = c.get("cluster_name") or ""
        count = c.get("count") or 0
        features = c.get("features") or {}

        suggested = _propose_label_mapping_for_cluster(cluster_name, features, labels_cfg)

        lines.append(f"## {cluster_id}")
        lines.append("")
        lines.append(f"Name suggestion: **{cluster_name}**")
        lines.append(f"Count: `{count}`")
        lines.append("")
        senders = features.get("domains_top") or features.get("senders_top") or []
        if senders:
            lines.append(f"Senders: `{senders[:3]}`")
        keywords = features.get("keywords") or []
        lines.append(f"Keywords: `{', '.join(keywords) if keywords else ''}`")

        att_types = [x["type"] for x in (features.get("attachment_types") or [])]
        lines.append(f"Attachments: `{', '.join(att_types) if att_types else 'none'}`")
        lines.append("")

        lines.append(f"Suggested label: **{suggested['suggested_label']}**")
        lines.append(f"Confidence: `{suggested['confidence']}`")
        lines.append(f"Rationale: `{', '.join(suggested.get('rationale') or [])}`")
        lines.append("")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_label_mapping_yaml_proposal(*, cluster_analysis: dict[str, Any], output_path: Path, labels_cfg: dict[str, Any]) -> None:
    mapping: dict[str, Any] = {"generated_at": datetime.now(timezone.utc).isoformat(), "clusters": {}}

    for c in cluster_analysis.get("clusters") or []:
        cid = c.get("cluster_id") or ""
        cluster_name = c.get("cluster_name") or ""
        features = c.get("features") or {}
        suggested = _propose_label_mapping_for_cluster(cluster_name, features, labels_cfg)

        mapping["clusters"][cid] = {
            "cluster_name": cluster_name,
            "count": c.get("count") or 0,
            "suggested_label": suggested["suggested_label"],
            "confidence": suggested["confidence"],
            "rationale": suggested.get("rationale") or [],
            # Approval step: leave as null so it's obvious you must approve/edit.
            "approved_label": None,
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(mapping, sort_keys=False), encoding="utf-8")


def _generate_rules_patch_from_approved_mapping(
    *,
    cluster_analysis: dict[str, Any],
    approved_mapping_path: Path,
    output_path: Path,
    labels_cfg: dict[str, Any],
) -> None:
    approved = yaml.safe_load(approved_mapping_path.read_text(encoding="utf-8")) or {}
    cluster_map = (approved.get("clusters") or {}) if isinstance(approved, dict) else {}

    # Translate cluster features into deterministic rule signals.
    # We generate ONLY a proposal patch file; it is not applied automatically.
    proposed: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rules_additions": {
            "permits": {"subject_keywords": [], "body_keywords": [], "attachment_filename_keywords": []},
            "driver_document": {"subject_keywords": [], "body_keywords": [], "attachment_filename_keywords": []},
            "mydot": {"subject_keywords": [], "body_keywords": [], "attachment_filename_keywords": []},
            "progressive_insurance": {"subject_keywords": [], "body_keywords": [], "attachment_filename_keywords": []},
        },
        "skipped_clusters": [],
    }

    # Helpers to pull keywords/attachments patterns.
    def _safe_list(x: Any) -> list[str]:
        if isinstance(x, list):
            return [str(i) for i in x if i]
        if isinstance(x, str):
            return [x]
        return []

    for c in cluster_analysis.get("clusters") or []:
        cid = c.get("cluster_id") or ""
        features = c.get("features") or {}
        cluster_name = c.get("cluster_name") or ""

        entry = cluster_map.get(cid) or {}
        approved_label = entry.get("approved_label")

        if not approved_label or approved_label not in ALLOWED_CLUSTER_LABELS:
            # Nothing approved.
            proposed["skipped_clusters"].append({"cluster_id": cid, "reason": "not_approved_or_unknown_label"})
            continue

        # Skip Needs Review clusters entirely (no rule generation).
        if approved_label == labels_cfg.get("canonical", {}).get("needs_review", "Needs Review"):
            proposed["skipped_clusters"].append({"cluster_id": cid, "reason": "needs_review_approved"})
            continue

        # Use the same keyword evidence the mapping used.
        keywords = [str(k) for k in (features.get("keywords") or []) if k]
        attachment_patterns = features.get("attachment_patterns") or []
        filenames = [p.get("filename") for p in attachment_patterns if isinstance(p, dict) and p.get("filename")]

        # Decide target signal based on approved label.
        if approved_label == labels_cfg.get("canonical", {}).get("permits", "Permits"):
            target = "permits"
        elif approved_label == labels_cfg.get("canonical", {}).get("mydot", "MYDOT"):
            target = "mydot"
        elif approved_label == labels_cfg.get("canonical", {}).get("progressive_insurance", "PROGRESSIVE COMMERCIAL INSURANCE"):
            target = "progressive_insurance"
        elif approved_label == labels_cfg.get("canonical", {}).get("driver_parent", "Driver Credentials / Documents"):
            target = "driver_document"
        else:
            proposed["skipped_clusters"].append({"cluster_id": cid, "reason": "unsupported_label"})
            continue

        # Populate subject/body keywords conservatively from cluster keywords.
        proposed["rules_additions"][target]["subject_keywords"] = sorted(
            list(set(proposed["rules_additions"][target]["subject_keywords"] + keywords))
        )
        proposed["rules_additions"][target]["body_keywords"] = sorted(
            list(set(proposed["rules_additions"][target]["body_keywords"] + keywords))
        )

        # Attachment filename keywords should come from repeated attachment patterns.
        fn_keywords = [f for f in filenames if f and any(ch.isalpha() for ch in f)]
        # Reduce to token-like fragments.
        fn_kws = []
        for f in fn_keywords:
            fn_kws.extend(_tokenize(f.replace("_", " ")))
        proposed["rules_additions"][target]["attachment_filename_keywords"] = sorted(
            list(set(proposed["rules_additions"][target]["attachment_filename_keywords"] + fn_kws))
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(proposed, sort_keys=False), encoding="utf-8")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Email inbox clustering (discovery only).")
    parser.add_argument("--mode", choices=["analysis", "propose-labels", "generate-rules"], default="analysis", help="analysis-only clustering + proposal artifacts.")
    parser.add_argument("--limit", type=int, default=300, help="Analyze last N emails (IMAP INBOX only).")
    parser.add_argument("--imap-timeout-sec", type=int, default=120, help="IMAP socket timeout for RFC822 fetch.")
    parser.add_argument("--fetch-retries", type=int, default=2, help="Retries per message fetch on failure.")
    parser.add_argument("--imap-secret-file", default="E:/secrets/gigatt imap.txt", help="IMAP secret file path.")
    parser.add_argument("--imap-host", default="imap.gmail.com", help="IMAP host.")
    parser.add_argument("--imap-port", type=int, default=993, help="IMAP port.")
    parser.add_argument("--merge-similarity", type=float, default=0.35, help="Jaccard merge threshold for grouping.")
    parser.add_argument("--cluster-analysis-json", default=str(_REPO_ROOT / "email_sorter" / "cluster_analysis.json"), help="cluster_analysis.json path.")
    parser.add_argument("--approved-mapping-file", default="", help="approved label mapping yaml (for rules proposal).")
    args = parser.parse_args(argv)

    labels_cfg = _load_labels_cfg()

    if args.mode == "analysis":
        emails, meta = _imap_scan_last_n_emails(
            imap_secret_file=args.imap_secret_file,
            imap_host=args.imap_host,
            imap_port=args.imap_port,
            limit=args.limit,
            imap_timeout_sec=args.imap_timeout_sec,
            fetch_retries=args.fetch_retries,
        )
        if not emails:
            raise SystemExit("No emails fetched from IMAP INBOX.")

        clusters = _cluster_emails(emails, merge_similarity=args.merge_similarity)

        out_md = _REPO_ROOT / "docs" / "EMAIL_CLUSTER_ANALYSIS.md"
        out_json = _REPO_ROOT / "email_sorter" / "cluster_analysis.json"
        # Build cluster analysis data once (used for both Markdown and JSON).
        analysis_clusters: list[dict[str, Any]] = []
        for idx, c in enumerate(clusters, start=1):
            cluster_name = _suggest_cluster_name(c)
            features = _cluster_features(c)
            emails_sample = [
                {
                    "message_id": e.message_id,
                    "sender": e.sender,
                    "sender_domain": e.sender_domain,
                    "subject": e.subject,
                    "snippet": e.snippet,
                    "attachment_types": e.attachment_types,
                    "attachment_filenames": e.attachment_filenames[:3],
                }
                for e in c[:5]
            ]
            analysis_clusters.append(
                {
                    "cluster_id": f"cluster_{idx:03d}",
                    "cluster_name": cluster_name,
                    "count": len(c),
                    "features": features,
                    "emails_sample": emails_sample,
                }
            )

        analysis_json = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "fetch_meta": meta,
            "clusters": analysis_clusters,
        }

        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(analysis_json, indent=2), encoding="utf-8")

        # Render Markdown from the already-computed analysis clusters.
        labels_cfg = _load_labels_cfg()
        lines: list[str] = []
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
        lines.append("# Email Cluster Analysis (Discovery Only)")
        lines.append("")
        lines.append(f"- Generated at: `{now}`")
        lines.append(f"- Cluster count: `{len(analysis_clusters)}`")
        lines.append("")

        for entry in analysis_clusters:
            cluster_name = entry.get("cluster_name") or ""
            features = entry.get("features") or {}
            suggested = _propose_label_mapping_for_cluster(cluster_name, features, labels_cfg)
            lines.append(f"## {entry.get('cluster_id')}")
            lines.append("")
            lines.append(f"Name suggestion: **{cluster_name}**")
            lines.append(f"Count: `{entry.get('count') or 0}`")
            lines.append("")

            lines.append("Key features:")
            lines.append("")
            domains_top = features.get("domains_top") or []
            senders_top = features.get("senders_top") or []
            if domains_top:
                lines.append(f"- Senders/domains: `{domains_top}`")
            elif senders_top:
                lines.append(f"- Senders/domains: `{senders_top}`")
            else:
                lines.append(f"- Senders/domains: `[]`")

            lines.append(f"- Keywords: `{', '.join(features.get('keywords') or [])}`")
            att_types = [x["type"] for x in (features.get("attachment_types") or [])]
            lines.append(f"- Attachment types: `{', '.join(att_types) if att_types else 'none'}`")
            lines.append("")

            attachment_patterns = features.get("attachment_patterns") or []
            if attachment_patterns:
                lines.append("Attachment patterns:")
                lines.append("")
                for p in attachment_patterns[:5]:
                    fn = p.get("filename") or ""
                    cnt = p.get("count") or 0
                    lines.append(f"- `{fn}` (x{cnt})")
                lines.append("")

            lines.append("Label suggestion (proposal only):")
            lines.append("")
            lines.append(f"- Suggested label: **{suggested['suggested_label']}**")
            lines.append(f"- Confidence: `{suggested['confidence']}`")
            lines.append(f"- Rationale: `{', '.join(suggested.get('rationale') or [])}`")
            lines.append("")

            lines.append("Sample emails:")
            lines.append("")
            for e in entry.get("emails_sample") or []:
                snippet = (e.get("snippet") or "").replace("\n", " ")[:120]
                lines.append(f"- `{e.get('message_id')}` | {(e.get('sender_domain') or e.get('sender') or '')}` | {(e.get('subject') or '')[:80]}")
                if snippet:
                    lines.append(f"  Body snippet: {snippet}")
            lines.append("")

        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

        print(f"Wrote: {out_md}")
        print(f"Wrote: {out_json}")
        return

    cluster_json_path = Path(args.cluster_analysis_json)
    cluster_analysis = _load_cluster_analysis_json(cluster_json_path)

    if args.mode == "propose-labels":
        out_md = _REPO_ROOT / "docs" / "EMAIL_CLUSTER_LABEL_SUGGESTIONS.md"
        out_yaml = _REPO_ROOT / "email_sorter" / "proposed_label_mapping.yaml"
        _write_label_suggestions_md(cluster_analysis=cluster_analysis, output_path=out_md, labels_cfg=labels_cfg)
        _write_label_mapping_yaml_proposal(cluster_analysis=cluster_analysis, output_path=out_yaml, labels_cfg=labels_cfg)
        print(f"Wrote: {out_md}")
        print(f"Wrote: {out_yaml}")
        return

    if args.mode == "generate-rules":
        if not args.approved_mapping_file:
            raise SystemExit("Missing --approved-mapping-file for generate-rules mode.")
        approved_path = Path(args.approved_mapping_file)
        if not approved_path.exists():
            raise SystemExit(f"Approved mapping file not found: {approved_path}")
        out_yaml = _REPO_ROOT / "email_sorter" / "proposed_rules_patch.yaml"
        _generate_rules_patch_from_approved_mapping(
            cluster_analysis=cluster_analysis,
            approved_mapping_path=approved_path,
            output_path=out_yaml,
            labels_cfg=labels_cfg,
        )
        print(f"Wrote: {out_yaml}")
        return


if __name__ == "__main__":
    main()

