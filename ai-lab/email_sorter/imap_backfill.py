from __future__ import annotations

import argparse
import base64
import imaplib
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from email import policy
from email.parser import BytesParser
from pathlib import Path
from typing import Any

from .backfill import (  # re-use Phase 1 logic helpers
    ALLOWED_CATEGORIES,
    ALLOWED_CATEGORIES as _ALLOWED_CATEGORIES,
    EmailRecord,
    _audit_writer_init,
    _call_ai_classifier,
    _compute_confidence_band,
    _decide_label_actions,
    _deterministic_classify,
    _extract_json_object,
    _load_yaml,
    _normalize_ws,
    _parse_email_sender,
    _propose_learning_rule_addition,
    _strip_html,
    _audit_write,
)


_AI_LAB_ROOT = Path(__file__).resolve().parents[1]


def _imap_secret_load(secret_file: Path) -> tuple[str, str]:
    """
    Expected format (based on E:/secrets/gigatt imap.txt):
      line1: password (may contain spaces; spaces are removed)
      line2: mailbox email/username
    """
    raw = secret_file.read_text(encoding="utf-8").splitlines()
    lines = [l.strip() for l in raw if l.strip()]
    if len(lines) < 2:
        raise ValueError(f"IMAP secret file must contain at least 2 non-empty lines: {secret_file}")
    pwd_raw = lines[0].replace(" ", "")
    username = lines[1]
    return username, pwd_raw


def _imap_format_since_utc(days: int) -> str:
    since_dt = datetime.now(timezone.utc) - timedelta(days=days)
    # IMAP SINCE uses format like: 18-Mar-2026
    return since_dt.strftime("%d-%b-%Y")


def _imap_parse_email(raw: bytes, *, imap_msg_id: str) -> tuple[EmailRecord, list[dict[str, Any]]]:
    """
    Returns:
      - EmailRecord for deterministic + AI classification
      - attachments_payload for worker offload (base64 for small pdf/images only)
    """
    msg = BytesParser(policy=policy.default).parsebytes(raw)

    from_header = msg.get("From", "") or ""
    subject = msg.get("Subject", "") or ""
    message_id_header = msg.get("Message-ID", "") or ""
    message_id_header = message_id_header.strip().strip("<>").strip()
    message_id = message_id_header or imap_msg_id

    sender_email, sender_domain = _parse_email_sender(from_header)

    # Body extraction: prefer text/plain, fall back to stripped HTML.
    plain_parts: list[str] = []
    html_parts: list[str] = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        ctype = (part.get_content_type() or "").lower()
        disp = (part.get_content_disposition() or "").lower()
        # Skip likely attachments; we'll handle them separately.
        if disp == "attachment":
            continue
        if ctype == "text/plain":
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                plain_parts.append(payload.decode(charset, errors="replace"))
            except Exception:
                plain_parts.append(payload.decode("utf-8", errors="replace"))
        elif ctype == "text/html":
            payload = part.get_payload(decode=True)
            if not payload:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                html_parts.append(payload.decode(charset, errors="replace"))
            except Exception:
                html_parts.append(payload.decode("utf-8", errors="replace"))

    if plain_parts:
        body_text = _normalize_ws("\n".join(plain_parts))
    elif html_parts:
        body_text = _normalize_ws(_strip_html("\n".join(html_parts)))
    else:
        body_text = ""

    attachment_filenames: list[str] = []
    attachment_mime_types: list[str] = []
    attachments_payload: list[dict[str, Any]] = []

    max_attachments = int(os.environ.get("EMAIL_SORTER_MAX_WORKER_ATTACHMENTS", "2"))
    max_attachment_bytes = int(os.environ.get("EMAIL_SORTER_MAX_WORKER_ATTACHMENT_BYTES", str(4 * 1024 * 1024)))

    for part in msg.walk():
        if part.is_multipart():
            continue
        filename = (part.get_filename() or "").strip()
        if not filename:
            disp = (part.get_content_disposition() or "").lower()
            if disp != "attachment":
                continue
            # Disposition says attachment but filename missing; skip to keep deterministic.
            continue

        ctype = (part.get_content_type() or "").strip()
        payload = part.get_payload(decode=True) or b""

        attachment_filenames.append(filename)
        attachment_mime_types.append(ctype)

        # For worker: only include pdf/image and only small enough payloads.
        fn_low = filename.lower()
        mt_low = (ctype or "").lower()
        is_pdf = mt_low == "application/pdf" or fn_low.endswith(".pdf")
        is_image = mt_low.startswith("image/") or any(fn_low.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"])
        if not (is_pdf or is_image):
            continue

        if len(payload) > max_attachment_bytes:
            attachments_payload.append(
                {
                    "filename": filename,
                    "mimeType": ctype,
                    "attachmentId": None,
                    "base64": None,
                    "note": f"attachment_truncated_or_omitted (bytes={len(payload)})",
                }
            )
            continue

        b64 = base64.b64encode(payload).decode("utf-8")
        attachments_payload.append(
            {
                "filename": filename,
                "mimeType": ctype,
                "attachmentId": None,
                "base64": b64,
            }
        )

        if len(attachments_payload) >= max_attachments:
            break

    email = EmailRecord(
        message_id=message_id,
        thread_id=None,
        from_header=from_header,
        sender_email=sender_email,
        sender_domain=sender_domain,
        subject=subject,
        snippet=(body_text[:200] if body_text else ""),
        body=body_text,
        attachment_filenames=attachment_filenames,
        attachment_ids=[],
        attachment_mime_types=attachment_mime_types,
        existing_label_names=[],
    )

    return email, attachments_payload


def _worker_document_intel_from_attachments(
    *,
    email: EmailRecord,
    attachments_payload: list[dict[str, Any]],
    worker_workflow_id: str,
    worker_name: str,
) -> tuple[str, float, list[str], str | None, bool]:
    """
    Worker n8n call. Best-effort; never raises.
    """
    try:
        from brain.worker_clients import worker_n8n_trigger  # type: ignore
    except Exception:
        return "needs_review", 0.0, ["worker_import_failed"], None, False

    payload = {
        "email": {
            "message_id": email.message_id,
            "from": email.from_header,
            "sender_email": email.sender_email,
            "sender_domain": email.sender_domain,
            "subject": email.subject,
            "body": (email.body or "")[:8000],
        },
        "attachments": attachments_payload,
        "hint": {"goal_categories": sorted(ALLOWED_CATEGORIES)},
    }

    try:
        out = worker_n8n_trigger(worker_workflow_id, payload, worker_name=worker_name)
    except Exception:
        return "needs_review", 0.0, ["worker_call_exception"], None, False

    if not isinstance(out, dict) or out.get("status") != "ok":
        return "needs_review", 0.0, ["worker_call_failed"], None, False

    data = out.get("data") or {}
    if isinstance(data, str):
        obj = _extract_json_object(data)
        data = obj or {}
    elif isinstance(data, dict) and "data" in data and isinstance(data["data"], dict):
        data = data["data"]

    cat = str((data.get("category") or "")).strip().lower()
    if cat not in _ALLOWED_CATEGORIES:
        cat = "needs_review"

    try:
        conf = float(data.get("confidence", 0.0))
    except Exception:
        conf = 0.0

    reasons = data.get("reasons") or []
    if isinstance(reasons, str):
        reasons = [reasons]
    if not isinstance(reasons, list):
        reasons = [str(reasons)]
    reasons = [str(r) for r in reasons][:10]

    driver_name = data.get("driver_name")
    if isinstance(driver_name, str):
        driver_name = driver_name.strip() or None
    else:
        driver_name = None

    return cat, round(conf, 3), reasons or ["worker_no_reasons"], driver_name, True


def imap_backfill_main(*, days: int, dry_run: bool, apply: bool, limit: int, imap_secret_file: str, imap_host: str, imap_port: int) -> None:
    if apply:
        raise SystemExit("IMAP backfill currently supports --dry-run only (no mailbox mutations).")

    if not dry_run:
        # Safety default
        dry_run = True

    config_dir = Path(__file__).resolve().parent / "config"
    labels_cfg = _load_yaml(config_dir / "labels.yaml")
    rules_cfg = _load_yaml(config_dir / "rules.yaml")
    thresholds = _load_yaml(config_dir / "thresholds.yaml")

    run_id = f"backfill_imap_dryrun_{int(time.time())}"
    report_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    logs_jsonl_path, audit_f = _audit_writer_init(_AI_LAB_ROOT, run_id)

    # Phase D scaffold: off-by-default learning proposals (no auto-apply).
    learning_enabled = str(os.environ.get("EMAIL_SORTER_ENABLE_LEARNING_LOOP", "")).strip().lower() in {"1", "true", "yes", "y"}
    learning_f = None
    learning_path = _AI_LAB_ROOT / "logs" / "email_sorter" / f"learning_rule_suggestions_{run_id}.jsonl"
    if learning_enabled:
        try:
            learning_path.parent.mkdir(parents=True, exist_ok=True)
            learning_f = learning_path.open("w", encoding="utf-8")
        except Exception:
            learning_f = None

    # IMAP login + select INBOX.
    secret_path = Path(imap_secret_file)
    username, password = _imap_secret_load(secret_path)

    imap = imaplib.IMAP4_SSL(imap_host, imap_port)
    imap.login(username, password)
    imap.select("INBOX")

    since_str = _imap_format_since_utc(days)
    # Pull message ids since the date. This approximates "last N days" without Gmail extensions.
    typ, data = imap.search(None, "SINCE", since_str)
    ids = []
    if isinstance(data, list) and data:
        ids = [int(x) for x in data[0].split() if x]
    ids = sorted(ids)[-limit:]

    summary = {
        "generated_at": report_ts,
        "days": days,
        "mode": "dry-run (imap)",
        "limit": limit,
        "processed": 0,
        "by_category": {},
        "by_band": {"high": 0, "medium": 0, "low": 0},
        "archive_proposed": 0,
        "ai_used_count": 0,
        "worker_used_count": 0,
        "needs_review": 0,
        "proposed_new_driver_child_labels": set(),
        "emails_needs_review_only": [],
        "emails_needs_review_all": [],
        "top_needs_review_unmatched": {},
        # category -> set of sender display strings for quick accuracy review
        "unique_senders_by_category": defaultdict(set),
    }

    ai_config = {
        "llm_base_url": os.environ.get("LLM_BASE_URL"),
        "llm_model": os.environ.get("LLM_MODEL"),
    }

    # Worker optional
    worker_workflow_id = os.environ.get("WORKER_N8N_WORKFLOW_ID_EMAIL_DOC_INTEL", "").strip()
    worker_name = os.environ.get("WORKER_N8N_WORKER_NAME", "worker-rig-01").strip()
    worker_enabled = bool(worker_workflow_id)

    existing_driver_child_labels: set[str] = set()  # IMAP mode can't inventory existing driver labels.

    try:
        for seq_id in ids:
            typ, fetched = imap.fetch(str(seq_id), "(RFC822)")
            raw = b""
            for part in fetched:
                if isinstance(part, tuple) and part[1]:
                    raw = part[1]
                    break
            if not raw:
                continue

            imap_msg_id = f"imap-{seq_id}"
            email, attachments_payload = _imap_parse_email(raw, imap_msg_id=imap_msg_id)

            deterministic = _deterministic_classify(email, rules=rules_cfg, thresholds=thresholds)

            ai_used = False
            worker_used = False

            heavy_doc = any((m or "").lower().startswith("image/") for m in email.attachment_mime_types) or any(
                (fn or "").lower().endswith(".pdf") for fn in email.attachment_filenames
            )

            final_category = deterministic.category
            final_conf = deterministic.confidence
            final_reasons = deterministic.evidence[:]
            final_driver_name = deterministic.driver_name

            high_t = float(thresholds.get("high", 0.90))
            medium_t = float(thresholds.get("medium", 0.72))

            # Permit PDFs/images: deterministic no longer labels "permits" — run document intel
            # *before* AI when we still have no category and the mail has PDF/image payloads.
            pre_worker_uncategorized = bool(
                worker_enabled
                and heavy_doc
                and final_category == "uncategorized"
                and str(os.environ.get("EMAIL_SORTER_WORKER_BEFORE_AI_UNCATEGORIZED_PDF", "1")).strip().lower()
                in {"1", "true", "yes", "y"}
            )
            if pre_worker_uncategorized:
                cat, conf, reasons, driver_name, ok = _worker_document_intel_from_attachments(
                    email=email,
                    attachments_payload=attachments_payload,
                    worker_workflow_id=worker_workflow_id,
                    worker_name=worker_name,
                )
                if ok and cat:
                    worker_used = True
                    final_category = cat
                    final_conf = conf
                    final_reasons = reasons or final_reasons
                    if driver_name:
                        final_driver_name = driver_name

            # AI wrapper only if we are not already high confidence (e.g. after doc intel).
            if final_conf < high_t:
                cat, conf, reasons, driver_name, ai_flag = _call_ai_classifier(
                    email=email,
                    deterministic=deterministic,
                    thresholds=thresholds,
                    config=ai_config,
                )
                ai_used = ai_flag
                final_category = cat
                final_conf = conf
                final_reasons = reasons
                final_driver_name = driver_name or deterministic.driver_name

                if deterministic.category == "loads" and final_category != "loads":
                    final_category = "loads"
                    final_conf = max(final_conf, medium_t + 0.02)
                    final_reasons = ["loads_channel_override"] + final_reasons

            # Worker offload in IMAP mode (optional; best-effort).
            worker_required = bool(heavy_doc and final_conf < medium_t and worker_enabled)
            if worker_required:
                cat, conf, reasons, driver_name, ok = _worker_document_intel_from_attachments(
                    email=email,
                    attachments_payload=attachments_payload,
                    worker_workflow_id=worker_workflow_id,
                    worker_name=worker_name,
                )
                if ok and cat:
                    worker_used = True
                    final_category = cat
                    final_conf = conf
                    final_reasons = reasons or final_reasons
                    if driver_name:
                        final_driver_name = driver_name

                if final_conf < medium_t:
                    final_category = "needs_review"
                    final_conf = 0.3

                if deterministic.category == "loads" and final_category != "loads":
                    final_category = "loads"
                    final_conf = max(final_conf, medium_t + 0.02)
                    final_reasons = ["loads_channel_override_after_worker"] + final_reasons

            band = _compute_confidence_band(final_conf, thresholds=thresholds)
            proposed_labels, proposed_archive, proposed_child_label, would_create_child = _decide_label_actions(
                category=final_category,
                confidence=final_conf,
                driver_name=final_driver_name,
                labels_cfg=labels_cfg,
                thresholds=thresholds,
                existing_driver_child_labels=existing_driver_child_labels,
            )

            if proposed_child_label and would_create_child:
                summary["proposed_new_driver_child_labels"].add(proposed_child_label)

            archive_executed = False

            summary["processed"] += 1
            summary["by_category"].setdefault(final_category, 0)
            summary["by_category"][final_category] += 1
            summary["by_band"][band] += 1
            if final_category == "needs_review" or proposed_labels == [labels_cfg["canonical"]["needs_review"]]:
                summary["needs_review"] += 1
                if len(summary["emails_needs_review_all"]) < 250:
                    summary["emails_needs_review_all"].append(
                        {
                            "message_id": email.message_id,
                            "sender": email.sender_email,
                            "sender_domain": email.sender_domain,
                            "subject": email.subject,
                            "deterministic_category": deterministic.category,
                            "confidence": final_conf,
                        }
                    )
                if proposed_labels == [labels_cfg["canonical"]["needs_review"]]:
                    if len(summary["emails_needs_review_only"]) < 50:
                        summary["emails_needs_review_only"].append(
                            {
                                "message_id": email.message_id,
                                "sender": email.sender_email,
                                "subject": email.subject,
                            }
                        )
                if deterministic.category == "uncategorized":
                    key = email.sender_domain or email.sender_email or "unknown"
                    summary["top_needs_review_unmatched"].setdefault(key, 0)
                    summary["top_needs_review_unmatched"][key] += 1

            if proposed_archive:
                summary["archive_proposed"] += 1
            if ai_used:
                summary["ai_used_count"] += 1
            if worker_used:
                summary["worker_used_count"] += 1

            # Unique senders per final category (email preferred; else From header snippet).
            sender_disp = (email.sender_email or "").strip()
            if not sender_disp:
                fh = (email.from_header or "").strip()
                sender_disp = fh[:120] if fh else ""
            if not sender_disp:
                sender_disp = f"(no-from) domain={email.sender_domain or 'unknown'}"
            summary["unique_senders_by_category"][final_category].add(sender_disp)

            decision_source = "worker" if worker_used else ("ai" if ai_used else "deterministic")

            audit_obj = {
                "generated_at": report_ts,
                "message_id": email.message_id,
                "thread_id": email.thread_id,
                "sender": email.sender_email,
                "sender_domain": email.sender_domain,
                "subject": email.subject,
                "category": final_category,
                "confidence": final_conf,
                "confidence_band": band,
                "deterministic_category": deterministic.category,
                "deterministic_confidence": deterministic.confidence,
                "deterministic_evidence": deterministic.evidence,
                "ai_used": ai_used,
                "worker_required": worker_required,
                "worker_used": worker_used,
                "decision_source": decision_source,
                "final_reasons": final_reasons,
                "matched_evidence": {
                    "attachments": email.attachment_filenames,
                    "sender_domain": email.sender_domain,
                    "deterministic_reasons": deterministic.reasons,
                },
                "proposed_labels": proposed_labels,
                "proposed_driver_child_label": proposed_child_label,
                "would_create_driver_child_label": would_create_child if dry_run else False,
                "proposed_archive": proposed_archive,
                "archive_executed": archive_executed,
                "dry_run": dry_run,
            }
            _audit_write(audit_f, audit_obj)

            # Phase D scaffold: propose rule keywords from high-confidence AI classifications.
            if learning_f is not None and ai_used and final_conf >= float(thresholds.get("high", 0.90)):
                try:
                    proposal = _propose_learning_rule_addition(
                        email=email,
                        category=final_category,
                        confidence=final_conf,
                        rules_cfg=rules_cfg,
                    )
                    if proposal:
                        _audit_write(learning_f, proposal)
                except Exception:
                    pass

    finally:
        audit_f.close()
        if learning_f is not None:
            learning_f.close()
        try:
            imap.logout()
        except Exception:
            pass

    # Write markdown report (same artifact paths as Phase 1 requirement).
    out_report_path = _AI_LAB_ROOT / "docs" / "EMAIL_BACKFILL_DRY_RUN_REPORT.md"
    out_report_path.parent.mkdir(parents=True, exist_ok=True)

    new_driver_list = sorted(list(summary["proposed_new_driver_child_labels"]))
    needs_review_only = summary["emails_needs_review_only"][:50]
    needs_review_all = summary["emails_needs_review_all"][:200]
    top_unmatched = sorted(summary["top_needs_review_unmatched"].items(), key=lambda kv: (-kv[1], kv[0]))[:25]

    needs_review_label = labels_cfg["canonical"]["needs_review"]

    lines: list[str] = []
    lines.append("# Email Backfill Dry-Run Report")
    lines.append("")
    lines.append(f"- Generated at: `{report_ts}`")
    lines.append(f"- Days window: `{days}`")
    lines.append(f"- Mode: `{summary['mode']}`")
    lines.append(f"- Limit: `{limit}`")
    lines.append(f"- Processed: `{summary['processed']}`")
    lines.append(f"- AI used: `{summary['ai_used_count']}`")
    lines.append(f"- Worker used: `{summary['worker_used_count']}`")
    lines.append("")
    lines.append("## Key Counts (Phase 1 dry-run)")
    lines.append("")
    lines.append(f"- Permits: `{summary['by_category'].get('permits', 0)}`")
    lines.append(f"- LOADS (PilotCarLoads): `{summary['by_category'].get('loads', 0)}`")
    lines.append(f"- Driver Credentials / Documents: `{summary['by_category'].get('driver_document', 0)}`")
    lines.append(f"- MYDOT: `{summary['by_category'].get('mydot', 0)}`")
    lines.append(f"- PROGRESSIVE COMMERCIAL INSURANCE: `{summary['by_category'].get('progressive_insurance', 0)}`")
    lines.append(f"- Needs Review: `{summary['needs_review']}`")
    lines.append(f"- Proposed archive count: `{summary['archive_proposed']}`")
    lines.append("")
    lines.append("## Summary by category")
    lines.append("")
    for cat, n in sorted(summary["by_category"].items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(f"- {cat}: {n}")
    lines.append("")
    lines.append("## Unique senders by final category (quick accuracy check)")
    lines.append("")
    lines.append("_One line per distinct sender (or From header) that landed in each category._")
    lines.append("")
    by_cat_senders: dict[str, set[str]] = summary["unique_senders_by_category"]
    for cat in sorted(by_cat_senders.keys(), key=lambda c: (-summary["by_category"].get(c, 0), c)):
        senders = sorted(by_cat_senders[cat], key=str.lower)
        lines.append(f"### `{cat}` ({len(senders)} unique)")
        lines.append("")
        if senders:
            for s in senders:
                lines.append(f"- {s}")
        else:
            lines.append("_none_")
        lines.append("")
    lines.append("## Summary by confidence band")
    lines.append("")
    lines.append(f"- high: {summary['by_band']['high']}")
    lines.append(f"- medium: {summary['by_band']['medium']}")
    lines.append(f"- low: {summary['by_band']['low']}")
    lines.append("")
    lines.append("## Archive proposals (proposed outcomes)")
    lines.append("")
    lines.append(f"- archive_proposed_count: {summary['archive_proposed']}")
    lines.append("")
    lines.append("## Needs Review details")
    lines.append("")
    lines.append(f"- Needs Review count (broad): {summary['needs_review']}")
    lines.append("")
    lines.append("## Emails routed to Needs Review (low-confidence only samples)")
    lines.append("")
    if needs_review_only:
        for item in needs_review_only:
            lines.append(f"- `{item['message_id']}` | {item['sender']} | {item['subject'][:80]}")
    else:
        lines.append("_No low-confidence-only Needs Review emails in this sample._")
    lines.append("")
    lines.append("## Emails routed to Needs Review (sample: first 200)")
    lines.append("")
    if needs_review_all:
        for item in needs_review_all:
            lines.append(
                f"- `{item['message_id']}` | {item['sender_domain'] or item['sender']} | {item['subject'][:80]} | deterministic={item['deterministic_category']} | conf={item['confidence']}"
            )
    else:
        lines.append("_No Needs Review emails in this sample._")
    lines.append("")
    lines.append("## Top unmatched senders/domains (Needs Review, deterministic uncategorized)")
    lines.append("")
    if top_unmatched:
        for k, v in top_unmatched:
            lines.append(f"- {k}: {v}")
    else:
        lines.append("_No unmatched deterministic-uncategorized Needs Review items._")
    lines.append("")
    lines.append("## Proposed new driver child labels (dry-run report-only)")
    lines.append("")
    if new_driver_list:
        for c in new_driver_list[:200]:
            lines.append(f"- {c}")
    else:
        lines.append("_No new driver child label proposals._")
    lines.append("")
    lines.append("## Audit log artifact")
    lines.append("")
    lines.append(f"- JSONL: `{logs_jsonl_path}`")
    lines.append("")

    out_report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote: {out_report_path}")
    print(f"Wrote: {logs_jsonl_path}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="IMAP-based dry-run backfill (Phase 1 unblock).")
    p.add_argument("--days", type=int, default=120, help="Look back N days.")
    p.add_argument("--dry-run", action="store_true", help="Dry-run only (default true).")
    p.add_argument("--apply", action="store_true", help="Not supported for IMAP yet.")
    p.add_argument("--limit", type=int, default=100, help="Max emails to process.")
    p.add_argument("--imap-secret-file", default="E:/secrets/gigatt imap.txt", help="IMAP creds file (password + email).")
    p.add_argument("--imap-host", default="imap.gmail.com", help="IMAP host.")
    p.add_argument("--imap-port", type=int, default=993, help="IMAP port.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    imap_backfill_main(
        days=args.days,
        dry_run=args.dry_run,
        apply=args.apply,
        limit=args.limit,
        imap_secret_file=args.imap_secret_file,
        imap_host=args.imap_host,
        imap_port=args.imap_port,
    )


if __name__ == "__main__":
    main()

