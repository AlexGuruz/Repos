from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


ALLOWED_CATEGORIES = {
    "permits",
    "loads",
    "mydot",
    "progressive_insurance",
    "driver_document",
    "bank_statement",
    "uncategorized",
    "needs_review",
}


_AI_LAB_ROOT = Path(__file__).resolve().parents[1]


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _normalize_ws(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _extract_json_object(text: str) -> dict[str, Any] | None:
    """
    Best-effort JSON extraction from model outputs that may include non-JSON
    prefix/suffix (e.g. transparency lines).
    """
    if not isinstance(text, str) or not text.strip():
        return None

    # Fast path: pure JSON.
    t = text.strip()
    if t.startswith("{") and t.endswith("}"):
        try:
            obj = json.loads(t)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass

    # Find the first {...} block.
    first = t.find("{")
    last = t.rfind("}")
    if first == -1 or last == -1 or last <= first:
        return None
    candidate = t[first : last + 1]
    try:
        obj = json.loads(candidate)
        if isinstance(obj, dict):
            return obj
    except Exception:
        return None
    return None


def _title_case_driver_name(name: str) -> str:
    """
    Heuristic title-casing for driver names.
    Avoids aggressive transformations; only normalizes whitespace.
    """
    n = _normalize_ws(name)
    if not n:
        return ""
    parts = re.split(r"\s+", n)
    return " ".join(p[:1].upper() + p[1:].lower() for p in parts if p)


def _parse_email_sender(from_header: str) -> tuple[str, str]:
    """
    Returns (email, domain).
    """
    if not from_header:
        return "", ""
    # Handles: "Name <email@domain.com>"
    m = re.search(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", from_header, flags=re.I)
    addr = m.group(1).strip().lower() if m else from_header.strip().lower()
    domain = ""
    if "@" in addr:
        domain = addr.split("@", 1)[1].strip().lower()
    return addr, domain


def _contains_any(haystack: str, needles: Iterable[str]) -> list[str]:
    """
    Returns the needles that were found (case-insensitive substring match).
    """
    found: list[str] = []
    h = (haystack or "").lower()
    for n in needles or []:
        nn = str(n or "").strip().lower()
        if not nn:
            continue
        if nn in h:
            found.append(nn)
    return found


def _tokenize_simple(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[a-zA-Z0-9]+", (text or "")) if len(t) >= 3]


def _propose_learning_rule_addition(
    *,
    email: EmailRecord,
    category: str,
    confidence: float,
    rules_cfg: dict[str, Any],
) -> dict[str, Any] | None:
    """
    Creates a proposal payload for adding deterministic keywords to rules.yaml.
    Never edits rules.yaml; caller writes this to a proposal log.
    """
    def _current_keywords(signal_key: str) -> set[str]:
        sig = rules_cfg.get(signal_key) or {}
        out: set[str] = set()
        for k in ("subject_keywords", "body_keywords", "attachment_filename_keywords"):
            for x in sig.get(k) or []:
                if x:
                    out.add(str(x).strip().lower())
        return out

    category_to_signal = {
        "permits": "permit_signals",
        "loads": "load_signals",
        "driver_document": "driver_document_signals",
        "mydot": "mydot_signals",
        "progressive_insurance": "progressive_insurance_signals",
    }
    if category not in category_to_signal:
        return None

    signal_key = category_to_signal[category]
    existing = _current_keywords(signal_key)

    subj = (email.subject or "")
    body = (email.body or "")
    subj_tokens = set(_tokenize_simple(subj))
    body_tokens = set(_tokenize_simple(body))
    filenames_tokens: set[str] = set()
    for fn in email.attachment_filenames or []:
        filenames_tokens.update(_tokenize_simple(fn.replace("_", " ").replace("-", " ")))

    # Conservative candidate tokens by category.
    candidate_by_category = {
        "permits": {"permit", "oversize", "over", "size", "route", "load", "dimensions", "effective", "issued", "trailer", "weight", "overweight"},
        "driver_document": {"driver", "cdl", "license", "credential", "credentials", "qualification", "mvr"},
        "mydot": {"mydot", "dot", "portal", "incident"},
        "progressive_insurance": {"progressive", "insurance", "policy", "premium", "commercial"},
        "loads": {"load", "alert", "pilot", "pilotcarloads", "dispatch"},
    }
    allowed = candidate_by_category.get(category) or set()

    subject_kws = sorted(list((subj_tokens | body_tokens) & allowed - existing))
    body_kws = sorted(list(body_tokens & allowed - existing))
    file_kws = sorted(list(filenames_tokens & allowed - existing))

    if not subject_kws and not body_kws and not file_kws:
        return None

    return {
        "message_id": email.message_id,
        "category": category,
        "confidence": confidence,
        "proposal": {
            signal_key: {
                "subject_keywords_add": subject_kws[:30],
                "body_keywords_add": body_kws[:30],
                "attachment_filename_keywords_add": file_kws[:30],
            }
        },
    }


def _extract_driver_name_deterministic(*, subject: str, body: str, filenames: list[str]) -> str | None:
    """
    Conservative driver-name extraction:
    - Prefer explicit patterns like "Driver: NAME" or "Driver Name - NAME".
    - For filenames, extract leftover tokens only when a credential keyword is present.
    """
    text = "\n".join([subject or "", body or ""]).strip()
    if not text:
        text = subject or ""

    # Driver: Jane Doe
    m = re.search(
        r"\b(?:driver|driver name|driver name\s*[:\-]|driver credentials?)\b\s*[:\-]\s*([A-Za-z]+(?:\s+[A-Za-z]+){0,3})",
        text,
        flags=re.I,
    )
    if m:
        return _title_case_driver_name(m.group(1))

    # Filename heuristic: only when a credential keyword is present.
    cred_tokens = {"cdl", "license", "credential", "credentials", "qualification", "mvr"}
    for fn in filenames or []:
        f = fn.replace("_", " ").replace("-", " ").strip()
        f_low = f.lower()
        if not any(tok in f_low for tok in cred_tokens):
            continue
        # Remove extension and common credential tokens; keep remaining title-case words.
        base = re.sub(r"\.[a-zA-Z0-9]+$", "", f)
        parts = [p for p in re.split(r"\s+", base) if p]
        filtered = []
        for p in parts:
            pl = p.lower()
            if pl in cred_tokens:
                continue
            if pl in {"doc", "docs", "document", "application", "pdf", "image", "scan", "signed"}:
                continue
            # Avoid single-letter tokens.
            if len(pl) >= 2:
                filtered.append(p)
        if len(filtered) >= 2:
            return _title_case_driver_name(" ".join(filtered[:4]))

    return None


@dataclass
class EmailRecord:
    message_id: str
    thread_id: str | None
    from_header: str
    sender_email: str
    sender_domain: str
    subject: str
    snippet: str
    body: str
    attachment_filenames: list[str]
    attachment_ids: list[str]
    attachment_mime_types: list[str]
    existing_label_names: list[str]


@dataclass
class DeterministicClassification:
    category: str
    confidence: float
    reasons: list[str]
    evidence: list[str]
    driver_name: str | None = None


def _sender_email_lc(email: EmailRecord) -> str:
    return (email.sender_email or "").strip().lower()


def _is_louisiana_dot_mydotd_notifier(email: EmailRecord) -> bool:
    """LA DOT MyDOTD traffic/incident mail — never classify as permits."""
    return _sender_email_lc(email) == "mydotd@info.la.gov"


def _is_louisiana_dot_trusted_sender(email: EmailRecord) -> bool:
    """LA DOT traffic notices (MyDOTD or info.la.gov)."""
    if _is_louisiana_dot_mydotd_notifier(email):
        return True
    return (email.sender_domain or "").strip().lower() == "info.la.gov"


def _deterministic_classify(email: EmailRecord, *, rules: dict[str, Any], thresholds: dict[str, float]) -> DeterministicClassification:
    priority = rules.get("priority_order") or []
    # Build a searchable string pool.
    subject_l = (email.subject or "").lower()
    body_l = (email.body or "").lower()
    filenames_l = " ".join([f or "" for f in (email.attachment_filenames or [])]).lower()

    sender_domain_hits = []

    for cat_key in priority:
        # Reset per category so sender_email_match evidence cannot leak across rules.
        sender_hits = []
        signals_key = None
        if cat_key == "loads":
            signals_key = "load_signals"
        elif cat_key == "driver_document":
            signals_key = "driver_document_signals"
        elif cat_key == "mydot":
            signals_key = "mydot_signals"
        elif cat_key == "progressive_insurance":
            signals_key = "progressive_insurance_signals"
        elif cat_key == "existing_obvious_business_labels":
            signals_key = "existing_obvious_business_label_signals"
        elif cat_key == "needs_review":
            # needs_review is the fallback
            continue
        else:
            continue

        signals = rules.get(signals_key) or {}

        # Specific category hit logic.
        evidence: list[str] = []
        subject_hits = _contains_any(subject_l, signals.get("subject_keywords") or [])
        body_hits = _contains_any(body_l, signals.get("body_keywords") or [])
        attach_hits = _contains_any(filenames_l, signals.get("attachment_filename_keywords") or [])

        # Sender/domains are optional in default config; keep them.
        sender_domains = signals.get("sender_domains") or []
        sender_emails = signals.get("sender_emails") or []
        domain_matches = []
        for d in sender_domains:
            dd = str(d).strip().lower()
            if not dd:
                continue
            if email.sender_domain and dd == email.sender_domain:
                domain_matches.append(dd)
        if domain_matches:
            evidence.append(f"sender_domain_match:{','.join(sorted(set(domain_matches)))}")

        if sender_emails:
            for se in sender_emails:
                if se and email.sender_email == str(se).strip().lower():
                    sender_hits.append(str(se).strip().lower())
        if sender_hits:
            evidence.append(f"sender_email_match:{','.join(sorted(set(sender_hits)))}")

        # Existing label keywords (optional).
        if signals_key == "existing_obvious_business_label_signals":
            # Only implement bank_statement sub-signals for now.
            bs_signals = (signals.get("bank_statement_signals") or {})
            bs_evidence = []
            bs_subject_hits = _contains_any(subject_l, bs_signals.get("subject_keywords") or [])
            bs_body_hits = _contains_any(body_l, bs_signals.get("body_keywords") or [])
            bs_attach_hits = _contains_any(filenames_l, bs_signals.get("attachment_filename_keywords") or [])
            if bs_subject_hits or bs_body_hits or bs_attach_hits:
                evidence = []
                if bs_subject_hits:
                    evidence.append(f"bank_statement_subject_hits:{','.join(sorted(set(bs_subject_hits)))}")
                if bs_body_hits:
                    evidence.append(f"bank_statement_body_hits:{','.join(sorted(set(bs_body_hits)))}")
                if bs_attach_hits:
                    evidence.append(f"bank_statement_attachment_hits:{','.join(sorted(set(bs_attach_hits)))}")

                # Confidence is conservative -> needs_review for dry-run.
                conf = thresholds.get("medium", 0.72)
                reasons = ["bank_statement_signals"]
                return DeterministicClassification(
                    category="bank_statement",
                    confidence=conf,
                    reasons=reasons,
                    evidence=evidence,
                    driver_name=None,
                )

        # For non-business label signals, decide if this category matches.
        if signals_key != "existing_obvious_business_label_signals":
            matched = bool(subject_hits or body_hits or attach_hits or evidence)
            if not matched:
                continue

            # Evidence scoring: keep it auditable and conservative.
            score = 0
            if subject_hits:
                score += 2 * len(set(subject_hits))
                evidence.append("subject_keyword_hits:" + ",".join(sorted(set(subject_hits))))
            if body_hits:
                score += 1 * len(set(body_hits))
                evidence.append("body_keyword_hits:" + ",".join(sorted(set(body_hits))))
            if attach_hits:
                score += 3 * len(set(attach_hits))
                evidence.append("attachment_filename_hits:" + ",".join(sorted(set(attach_hits))))
            if domain_matches:
                score += 3

            # Priority-first behavior:
            # - driver_document: never let it be low when any credential signal matched.
            # - others: can be medium.
            high_t = float(thresholds.get("high", 0.90))
            medium_t = float(thresholds.get("medium", 0.72))

            # Determine confidence.
            if cat_key == "loads":
                # PilotCarLoads / pilotcarloads.com — operational load alerts, not permit PDFs.
                if not (sender_hits or domain_matches):
                    continue
                conf = high_t if (sender_hits or domain_matches) else medium_t
                return DeterministicClassification(
                    category="loads",
                    confidence=round(float(conf), 3),
                    reasons=["load_signals"],
                    evidence=evidence + ["loads:pilotcarloads_channel"],
                )

            if cat_key == "driver_document":
                # Extract driver name only when credential evidence exists.
                driver_name = _extract_driver_name_deterministic(
                    subject=email.subject, body=email.body, filenames=email.attachment_filenames
                )
                strong = bool(attach_hits) and (subject_hits or body_hits)
                if strong:
                    conf = min(0.96, max(high_t, 0.91))
                else:
                    conf = medium_t + 0.01
                return DeterministicClassification(
                    category="driver_document",
                    confidence=round(conf, 3),
                    reasons=["driver_document_signals"],
                    evidence=evidence,
                    driver_name=driver_name,
                )

            if cat_key == "mydot":
                # Do not classify as MYDOT from broad body keywords alone (e.g. "parish" in PilotCarLoads).
                official_dot = bool(sender_hits) and signals_key == "mydot_signals"
                trusted_la = _is_louisiana_dot_trusted_sender(email)
                if (
                    body_hits
                    and not subject_hits
                    and not attach_hits
                    and not domain_matches
                    and not official_dot
                    and not trusted_la
                ):
                    continue
                conf = high_t if subject_hits or attach_hits or official_dot or trusted_la else medium_t
                return DeterministicClassification(
                    category="mydot",
                    confidence=round(float(conf), 3),
                    reasons=["mydot_signals"],
                    evidence=evidence,
                )

            if cat_key == "progressive_insurance":
                # Avoid classifying generic "insurance"/"commercial" marketing as Progressive.
                dom_l = (email.sender_domain or "").strip().lower()
                progressive_dom = dom_l in {"e.progressive.com", "progressive.com"} or dom_l.endswith(
                    ".progressive.com"
                )
                brand = "progressive" in subject_l or "progressive" in body_l
                if not progressive_dom and not brand:
                    continue
                conf = high_t if subject_hits and (body_hits or attach_hits) else medium_t
                return DeterministicClassification(
                    category="progressive_insurance",
                    confidence=round(float(conf), 3),
                    reasons=["progressive_insurance_signals"],
                    evidence=evidence,
                )

    # If nothing matched, fallback.
    return DeterministicClassification(
        category="uncategorized",
        confidence=0.25,
        reasons=["no_deterministic_match"],
        evidence=[],
        driver_name=None,
    )


def _map_category_to_primary_labels(*, category: str, labels_cfg: dict[str, Any]) -> list[str]:
    canonical = labels_cfg.get("canonical") or {}
    if category == "permits":
        return [canonical.get("permits", "Permits")]
    if category == "loads":
        return [canonical.get("loads", "LOADS")]
    if category == "mydot":
        return [canonical.get("mydot", "MYDOT")]
    if category == "progressive_insurance":
        return [canonical.get("progressive_insurance", "PROGRESSIVE COMMERCIAL INSURANCE")]
    if category == "driver_document":
        return [canonical.get("driver_parent", "Driver Credentials / Documents")]
    # bank_statement and uncategorized route via fallback label(s).
    fallbacks = labels_cfg.get("category_label_fallbacks") or {}
    if category in fallbacks:
        return [fallbacks[category]]
    # needs_review is always Needs Review.
    if category == "needs_review":
        return [canonical.get("needs_review", "Needs Review")]
    return [canonical.get("needs_review", "Needs Review")]


def _compute_confidence_band(conf: float, *, thresholds: dict[str, float]) -> str:
    high_t = float(thresholds.get("high", 0.90))
    medium_t = float(thresholds.get("medium", 0.72))
    if conf >= high_t:
        return "high"
    if conf >= medium_t:
        return "medium"
    return "low"


def _decide_label_actions(*, category: str, confidence: float, driver_name: str | None, labels_cfg: dict[str, Any], thresholds: dict[str, float], existing_driver_child_labels: set[str]) -> tuple[list[str], bool, str | None, bool]:
    """
    Returns:
      (proposed_labels, proposed_archive, proposed_driver_child_label, would_create_driver_child_label)
    """
    canonical = labels_cfg.get("canonical") or {}
    needs_review_label = canonical.get("needs_review", "Needs Review")
    driver_parent = canonical.get("driver_parent", "Driver Credentials / Documents")
    driver_create_t = float(thresholds.get("driver_create", 0.94))

    band = _compute_confidence_band(confidence, thresholds=thresholds)

    # Primary labels (category-specific).
    primary = _map_category_to_primary_labels(category=category, labels_cfg=labels_cfg)

    # Low confidence => Needs Review only.
    if band == "low" or category == "needs_review":
        return [needs_review_label], False, None, False

    # Medium confidence => primary + Needs Review, no archive.
    if band == "medium":
        labels = list(dict.fromkeys([*primary, needs_review_label]))
        # Driver child label is not created unless extremely high confidence; for medium we won't propose child.
        return labels, False, None, False

    # High confidence => primary only, archive allowed.
    labels = list(dict.fromkeys(primary))
    proposed_child: str | None = None
    would_create_child = False

    if category == "driver_document" and driver_name:
        proposed_child = f"{driver_parent}/{_title_case_driver_name(driver_name)}"
        if confidence >= driver_create_t:
            if proposed_child not in existing_driver_child_labels:
                # Dry-run: never create; only report.
                would_create_child = True
        else:
            # Driver confidence not high enough for child label: no child label.
            proposed_child = None
            would_create_child = False

        # For dry-run, we report the child label even if it doesn't exist yet.
        # For apply mode, the caller can choose to create based on would_create_child.
        if proposed_child:
            labels.append(proposed_child)

    return labels, True, proposed_child, would_create_child


def _call_ai_classifier(*, email: EmailRecord, deterministic: DeterministicClassification, thresholds: dict[str, float], config: dict[str, Any]) -> tuple[str, float, list[str], str | None, bool]:
    """
    Returns:
      (category, confidence, reasons, driver_name, ai_used)
    """
    session_id = f"email-sorter-backfill-{int(time.time())}"

    # Optional hard gate: skip AI entirely if no LLM routing config exists.
    # This prevents Phase 1 dry-runs from hanging when LLM endpoints are not configured.
    if str(os.environ.get("EMAIL_SORTER_DISABLE_AI", "")).strip().lower() in {"1", "true", "yes", "y"}:
        return (
            deterministic.category,
            deterministic.confidence,
            ["ai_disabled_by_env"],
            deterministic.driver_name,
            False,
        )

    llm_base_url = str(config.get("llm_base_url") or os.environ.get("LLM_BASE_URL") or "").strip()
    # Allow worker/ollama host wiring to drive the same orchestrator path.
    if not llm_base_url:
        ollama_host = str(os.environ.get("OLLAMA_HOST") or "").strip().rstrip("/")
        if ollama_host:
            if ollama_host.endswith("/v1"):
                llm_base_url = ollama_host
            else:
                llm_base_url = f"{ollama_host}/v1"
    # Final fallback: local LM Studio/OpenAI-compatible endpoint on this machine.
    if not llm_base_url:
        llm_base_url = "http://127.0.0.1:1234/v1"

    # Load orchestrator.
    try:
        sys.path.insert(0, str(_AI_LAB_ROOT))
        from brain.orchestrator.main import run as orchestrator_run  # type: ignore
    except Exception:
        return (
            deterministic.category,
            deterministic.confidence,
            ["ai_import_failed_fallback_to_deterministic"],
            deterministic.driver_name,
            False,
        )
    llm_model = str(config.get("llm_model") or os.environ.get("LLM_MODEL") or "Qwen2.5-Coder-14B-Instruct")

    categories_hint = ", ".join(sorted(ALLOWED_CATEGORIES))

    # Provide a bounded amount of content; attachments are filename-only for dry-run.
    body_excerpt = (email.body or "").strip()
    body_excerpt = body_excerpt[:8000]
    prompt = (
        "Classify this email into exactly one category.\n"
        "Prefer 'needs_review' over wrong classification.\n\n"
        "Category 'permits': use ONLY for oversize/transport **permit documents** (PDF or image attachments "
        "whose content is actually a permit — e.g. issued permit, route, dimensions, permit number). "
        "Do NOT use 'permits' for PilotCarLoads-style load alerts (those are 'loads' if from pilotcarloads.com "
        "or generic operational mail). You only see attachment **filenames** here, not file contents — if filenames "
        "are vague but the email clearly references a permit document, you may still choose 'permits' with "
        "lower confidence; when uncertain, use 'needs_review'.\n\n"
        f"Allowed categories: {categories_hint}\n\n"
        "Output JSON ONLY (no markdown, no extra text). Must match this schema:\n"
        "{\n"
        '  "category": "<one of allowed categories>",\n'
        '  "confidence": <number 0.0-1.0>,\n'
        '  "reasons": ["<short reason>", ...],\n'
        '  "driver_name": "<string or null>",\n'
        '  "should_create_driver_label": <boolean>,\n'
        '  "suggested_labels": ["<label-name>", ...]\n'
        "}\n\n"
        "Email fields:\n"
        f"- sender: {email.from_header}\n"
        f"- sender_domain: {email.sender_domain}\n"
        f"- subject: {email.subject}\n"
        f"- snippet: {email.snippet}\n"
        f"- body_excerpt: {body_excerpt}\n"
        f"- attachment_filenames: {email.attachment_filenames}\n\n"
        "Deterministic results already computed (may be wrong; use to guide only):\n"
        f"- deterministic_category: {deterministic.category}\n"
        f"- deterministic_confidence: {deterministic.confidence}\n"
        f"- deterministic_reasons: {deterministic.reasons}\n"
        f"- deterministic_evidence: {deterministic.evidence}\n"
    )

    try:
        out = orchestrator_run(prompt, llm_base_url=llm_base_url, llm_model=llm_model, session_id=session_id)
        reply = out.get("reply") if isinstance(out, dict) else None
    except Exception:
        return (
            deterministic.category,
            deterministic.confidence,
            ["ai_call_failed_fallback_to_deterministic"],
            deterministic.driver_name,
            False,
        )

    obj = _extract_json_object(reply or "")
    if not obj:
        return (
            deterministic.category,
            deterministic.confidence,
            ["ai_output_invalid_json_fallback_to_deterministic"],
            deterministic.driver_name,
            False,
        )

    cat = str(obj.get("category") or "").strip().lower()
    conf_raw = obj.get("confidence")
    try:
        conf = float(conf_raw)
    except Exception:
        conf = 0.0

    reasons = obj.get("reasons") or []
    if not isinstance(reasons, list):
        reasons = [str(reasons)]
    reasons = [str(r) for r in reasons][:10]

    driver_name = obj.get("driver_name")
    if isinstance(driver_name, str):
        driver_name = driver_name.strip() or None
    else:
        driver_name = None

    if cat not in ALLOWED_CATEGORIES:
        cat = "needs_review"

    return cat, round(conf, 3), reasons or ["ai_no_reasons"], driver_name, True


def _try_worker_document_intel(
    *,
    service: Any,
    email: EmailRecord,
    worker_workflow_id: str,
    worker_name: str,
) -> tuple[str, float, list[str], str | None, bool]:
    """
    Attempts heavy doc inspection on the worker via n8n.

    Worker is expected to return a JSON-ish classification object.
    We keep this best-effort and fall back to deterministic/AI if it fails.
    """
    try:
        from brain.worker_clients import worker_n8n_trigger  # type: ignore
    except Exception:
        return "needs_review", 0.0, ["worker_import_failed"], None, False

    # Only ship attachment content for likely doc-heavy types.
    max_attachments = int(os.environ.get("EMAIL_SORTER_MAX_WORKER_ATTACHMENTS", "2"))
    max_attachment_bytes = int(os.environ.get("EMAIL_SORTER_MAX_WORKER_ATTACHMENT_BYTES", str(4 * 1024 * 1024)))

    attachments_payload: list[dict[str, Any]] = []
    for i in range(min(max_attachments, len(email.attachment_filenames or []))):
        fn = (email.attachment_filenames[i] or "").lower()
        mt = (email.attachment_mime_types[i] or "").lower()
        aid = (email.attachment_ids[i] or "").strip()
        if not aid:
            continue
        # Heuristic: only include images and PDFs.
        is_pdf = mt == "application/pdf" or fn.endswith(".pdf")
        is_image = mt.startswith("image/") or any(fn.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp"])
        if not (is_pdf or is_image):
            continue

        b64url = _gmail_get_attachment_base64(service, message_id=email.message_id, attachment_id=aid)
        if not b64url:
            continue

        # Rough byte estimate for safety without decoding large blobs.
        approx_bytes = int(len(b64url) * 3 / 4)
        if approx_bytes > max_attachment_bytes:
            attachments_payload.append(
                {
                    "filename": email.attachment_filenames[i],
                    "mimeType": email.attachment_mime_types[i],
                    "attachmentId": aid,
                    "base64": None,
                    "note": f"attachment_truncated_or_omitted (approx_bytes={approx_bytes})",
                }
            )
            continue

        attachments_payload.append(
            {
                "filename": email.attachment_filenames[i],
                "mimeType": email.attachment_mime_types[i],
                "attachmentId": aid,
                "base64": b64url,
            }
        )

    payload = {
        "email": {
            "message_id": email.message_id,
            "thread_id": email.thread_id,
            "from": email.from_header,
            "sender_email": email.sender_email,
            "sender_domain": email.sender_domain,
            "subject": email.subject,
            "snippet": email.snippet,
            "body": (email.body or "")[:8000],
        },
        "attachments": attachments_payload,
        "hint": {
            "deterministic_category": None,
            "goal_categories": sorted(ALLOWED_CATEGORIES),
        },
    }

    # Worker call requires the n8n client; since we don't have a Gmail service here,
    # we intentionally only pass attachment metadata in this Phase 1 skeleton.
    out = worker_n8n_trigger(worker_workflow_id, payload, worker_name=worker_name)
    if not isinstance(out, dict) or out.get("status") != "ok":
        return "needs_review", 0.0, ["worker_call_failed"], None, True

    data = out.get("data") or {}
    # Try common shapes.
    if isinstance(data, str):
        obj = _extract_json_object(data)
        data = obj or {}
    elif isinstance(data, dict):
        # unwrap
        if "result" in data and isinstance(data["result"], dict):
            data = data["result"]
        elif "classification" in data and isinstance(data["classification"], dict):
            data = data["classification"]

    cat = str((data.get("category") or "")).strip().lower()
    if cat not in ALLOWED_CATEGORIES:
        cat = "needs_review"

    conf_raw = data.get("confidence", 0.0)
    try:
        conf = float(conf_raw)
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


def _label_list_to_set(labels_cfg: dict[str, Any]) -> dict[str, str]:
    canonical = labels_cfg.get("canonical") or {}
    mapping = {
        "Permits": canonical.get("permits", "Permits"),
        "MYDOT": canonical.get("mydot", "MYDOT"),
        "PROGRESSIVE COMMERCIAL INSURANCE": canonical.get("progressive_insurance", "PROGRESSIVE COMMERCIAL INSURANCE"),
        "Driver Credentials / Documents": canonical.get("driver_parent", "Driver Credentials / Documents"),
        "Needs Review": canonical.get("needs_review", "Needs Review"),
    }
    return mapping


def _decode_base64_url(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _strip_html(html: str) -> str:
    # Very light stripping; keep determinism and avoid heavy deps.
    s = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _iter_payload_parts(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """
    Recursively yields MIME parts.
    """
    if not isinstance(payload, dict):
        return
    yield payload
    for p in payload.get("parts", []) or []:
        if isinstance(p, dict):
            yield from _iter_payload_parts(p)


def _extract_text_from_gmail_payload(payload: dict[str, Any]) -> str:
    plain_parts: list[str] = []
    html_parts: list[str] = []
    for part in _iter_payload_parts(payload):
        mime = (part.get("mimeType") or "").lower()
        body = part.get("body") or {}
        data = body.get("data")
        if not data:
            continue
        try:
            decoded = _decode_base64_url(data).decode("utf-8", errors="replace")
        except Exception:
            continue
        if mime == "text/plain":
            plain_parts.append(decoded)
        elif mime == "text/html":
            html_parts.append(decoded)

    if plain_parts:
        return _normalize_ws("\n".join(plain_parts))
    if html_parts:
        return _normalize_ws(_strip_html("\n".join(html_parts)))
    return ""


def _extract_attachment_metadata(payload: dict[str, Any]) -> list[dict[str, str]]:
    """
    Returns attachment metadata without downloading content.
    """
    out: list[dict[str, str]] = []
    for part in _iter_payload_parts(payload):
        filename = (part.get("filename") or "").strip()
        body = part.get("body") or {}
        attachment_id = body.get("attachmentId")
        mime = part.get("mimeType") or ""
        if not filename or not attachment_id:
            continue
        out.append({"filename": filename, "attachmentId": attachment_id, "mimeType": mime})
    return out


def _gmail_labels_index(service: Any) -> dict[str, str]:
    """
    Returns mapping labelId -> labelName
    """
    resp = service.users().labels().list(userId="me").execute()
    labels = resp.get("labels", []) or []
    out: dict[str, str] = {}
    for l in labels:
        lid = l.get("id") or ""
        name = l.get("name") or ""
        if lid and name:
            out[str(lid)] = str(name)
    return out


def _gmail_fetch_messages(service: Any, *, q: str, limit: int) -> list[dict[str, str]]:
    """
    Returns list of {"id": ..., "threadId": ...}
    """
    out: list[dict[str, str]] = []
    page_token: str | None = None
    while True:
        kwargs: dict[str, Any] = {
            "userId": "me",
            "maxResults": min(100, max(1, limit - len(out))),
            "q": q,
            "labelIds": ["INBOX"],
        }
        if page_token:
            kwargs["pageToken"] = page_token
        resp = service.users().messages().list(**kwargs).execute()
        msgs = resp.get("messages", []) or []
        for m in msgs:
            mid = m.get("id") or ""
            if not mid:
                continue
            # threadId isn't returned by list; fetch metadata later.
            out.append({"id": mid, "threadId": ""})
            if len(out) >= limit:
                return out
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
        if len(out) >= limit:
            break
    return out


def _gmail_get_message_full(service: Any, *, message_id: str) -> dict[str, Any]:
    return service.users().messages().get(userId="me", id=message_id, format="full").execute()


def _gmail_get_message_metadata(service: Any, *, message_id: str) -> dict[str, Any]:
    return service.users().messages().get(userId="me", id=message_id, format="metadata").execute()


def _gmail_get_attachment_base64(service: Any, *, message_id: str, attachment_id: str) -> str | None:
    """
    Fetch attachment base64 payload from Gmail.
    Returns base64url string (not decoded).
    """
    resp = (
        service.users()
        .messages()
        .attachments()
        .get(userId="me", messageId=message_id, id=attachment_id)
        .execute()
    )
    return resp.get("data")


def _gmail_get_header_value(headers: list[dict[str, str]], key: str) -> str:
    key_l = key.lower()
    for h in headers or []:
        if (h.get("name") or "").lower() == key_l:
            return h.get("value") or ""
    return ""


def _audit_writer_init(base_dir: Path, run_id: str) -> tuple[Path, Any]:
    out_dir = base_dir / "logs" / "email_sorter"
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / f"{run_id}.jsonl"
    f = jsonl_path.open("w", encoding="utf-8")
    return jsonl_path, f


def _audit_write(f: Any, obj: dict[str, Any]) -> None:
    f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    f.flush()


def _gmail_existing_driver_child_labels(*, existing_label_names: list[str], driver_parent: str) -> set[str]:
    prefix = driver_parent.strip() + "/"
    out = set()
    for name in existing_label_names or []:
        n = str(name or "")
        if n.startswith(prefix):
            out.add(n)
    return out


def _title_case_from_driver_name_for_label(driver_name: str) -> str:
    # Keep commas etc? Replace with spaces; keep simple.
    clean = re.sub(r"[^A-Za-z\s]", " ", driver_name or "")
    clean = _title_case_driver_name(clean)
    return clean


def _build_driver_child_label(driver_parent: str, driver_name: str) -> str:
    parent = (driver_parent or "").strip()
    dn = _title_case_from_driver_name_for_label(driver_name)
    return f"{parent}/{dn}".strip("/")


def backfill_main(*, days: int, dry_run: bool, apply: bool, limit: int) -> None:
    """
    Implements Phase 1 dry-run backfill.
    """
    if apply and dry_run:
        raise SystemExit("Choose only one of --dry-run or --apply.")

    if not dry_run and not apply:
        dry_run = True

    config_dir = Path(__file__).resolve().parent / "config"
    labels_cfg = _load_yaml(config_dir / "labels.yaml")
    rules_cfg = _load_yaml(config_dir / "rules.yaml")
    thresholds = _load_yaml(config_dir / "thresholds.yaml")

    run_id = f"backfill_{'dryrun' if dry_run else 'apply'}_{int(time.time())}"
    report_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    # Set up audit log file.
    logs_jsonl_path, audit_f = _audit_writer_init(_AI_LAB_ROOT, run_id)

    # Phase D scaffold: off-by-default rule learning proposals (no auto-apply).
    learning_enabled = str(os.environ.get("EMAIL_SORTER_ENABLE_LEARNING_LOOP", "")).strip().lower() in {"1", "true", "yes", "y"}
    learning_f = None
    learning_path = _AI_LAB_ROOT / "logs" / "email_sorter" / f"learning_rule_suggestions_{run_id}.jsonl"
    if learning_enabled:
        try:
            learning_path.parent.mkdir(parents=True, exist_ok=True)
            learning_f = learning_path.open("w", encoding="utf-8")
        except Exception:
            learning_f = None

    # Log worker offload unavailability early (dry-run should never crash).
    worker_workflow_id = os.environ.get("WORKER_N8N_WORKFLOW_ID_EMAIL_DOC_INTEL", "").strip()
    worker_offload_available = bool(worker_workflow_id)
    if not worker_workflow_id:
        try:
            from brain import telemetry  # type: ignore

            telemetry.log_event("email_sorter_worker_offload_unavailable", detail="WORKER_N8N_WORKFLOW_ID_EMAIL_DOC_INTEL not set")
        except Exception:
            pass

    # Gmail adapter: full checkout under Ai/, or bundled portable copy (no nested .git).
    _legacy_agent = _AI_LAB_ROOT / "Ai" / "Email-Inbox-Agent---Doo-Made"
    _portable_agent = _AI_LAB_ROOT / "email_sorter" / "gmail_portable"
    if (_legacy_agent / "app" / "gmail_client.py").exists():
        agent_root = _legacy_agent
    elif (_portable_agent / "app" / "gmail_client.py").exists():
        agent_root = _portable_agent
    else:
        raise FileNotFoundError(
            "Gmail adapter not found. Clone ai-lab with email_sorter/gmail_portable, "
            "or add Ai/Email-Inbox-Agent---Doo-Made.\n"
            f"Expected one of:\n- {_legacy_agent / 'app' / 'gmail_client.py'}\n- {_portable_agent / 'app' / 'gmail_client.py'}"
        )
    sys.path.insert(0, str(agent_root))
    from app import gmail_client as gmail_client_mod  # type: ignore
    from app.gmail_client import get_gmail_service, get_or_create_label_id  # type: ignore

    # Fail early with clear credential file paths before doing any mailbox work.
    if hasattr(gmail_client_mod, "preflight_gmail_auth"):
        preflight = gmail_client_mod.preflight_gmail_auth()  # type: ignore[attr-defined]
        if not preflight.get("ok"):
            raise FileNotFoundError(
                "Gmail auth preflight failed (missing credentials/token).\n"
                + json.dumps(preflight, ensure_ascii=False, indent=2)
            )

    try:
        service = get_gmail_service()
    except FileNotFoundError as exc:
        msg = (
            "Missing Gmail OAuth credentials for Gmail API access.\n"
            f"{exc}\n\n"
            "Fix: create `credentials.json` next to the Gmail adapter (or under email_sorter/gmail_portable/) "
            "or set env vars:\n"
            "- `GOOGLE_CREDENTIALS_FILE` (absolute path to OAuth client JSON)\n"
            "- `GOOGLE_TOKEN_FILE` (absolute path to stored token.json)\n"
        )
        print(msg)
        raise
    label_id_to_name = _gmail_labels_index(service)
    existing_label_names = list(label_id_to_name.values())

    canonical = labels_cfg.get("canonical") or {}
    driver_parent = canonical.get("driver_parent", "Driver Credentials / Documents")
    needs_review_label = canonical.get("needs_review", "Needs Review")
    existing_driver_child_labels = _gmail_existing_driver_child_labels(
        existing_label_names=existing_label_names, driver_parent=driver_parent
    )

    # Gmail query: last N days in inbox. Use Gmail search for bounded scope.
    q = f"newer_than:{int(days)}d"
    # Optional: avoid messages already labeled with Needs Review + main categories.
    # For dry-run Phase 1, we keep broad coverage to validate behavior quality.

    message_refs = _gmail_fetch_messages(service, q=q, limit=limit)

    # Preload full message details for threads and bodies; we keep it simple.
    summary = {
        "generated_at": report_ts,
        "days": days,
        "mode": "dry-run" if dry_run else "apply",
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
    }

    ai_config = {
        "llm_base_url": os.environ.get("LLM_BASE_URL"),
        "llm_model": os.environ.get("LLM_MODEL"),
    }

    for ref in message_refs:
        message_id = ref.get("id") or ""
        if not message_id:
            continue

        # Fetch message full for body + attachments.
        meta = _gmail_get_message_metadata(service, message_id=message_id)
        thread_id = meta.get("threadId") or None
        label_ids = meta.get("labelIds") or []
        existing_names = [label_id_to_name.get(str(lid)) for lid in label_ids if str(lid) in label_id_to_name]

        full = _gmail_get_message_full(service, message_id=message_id)
        payload = full.get("payload") or {}
        headers = payload.get("headers") or full.get("payload", {}).get("headers") or []

        subject = _gmail_get_header_value(headers, "Subject")
        from_header = _gmail_get_header_value(headers, "From")
        snippet = (full.get("snippet") or "") if isinstance(full, dict) else ""

        sender_email, sender_domain = _parse_email_sender(from_header)
        body_text = _extract_text_from_gmail_payload(payload)

        attachments = _extract_attachment_metadata(payload)
        attachment_filenames = [a.get("filename") or "" for a in attachments]
        attachment_ids = [a.get("attachmentId") or "" for a in attachments]
        attachment_mime_types = [a.get("mimeType") or "" for a in attachments]

        email = EmailRecord(
            message_id=message_id,
            thread_id=thread_id,
            from_header=from_header,
            sender_email=sender_email,
            sender_domain=sender_domain,
            subject=subject,
            snippet=snippet,
            body=body_text,
            attachment_filenames=attachment_filenames,
            attachment_ids=attachment_ids,
            attachment_mime_types=attachment_mime_types,
            existing_label_names=[str(x) for x in existing_names if x],
        )

        deterministic = _deterministic_classify(email, rules=rules_cfg, thresholds=thresholds)

        ai_used = False
        worker_used = False

        # Worker heuristic: in Phase 1 dry-run, we don't have reliable local OCR.
        # We mark worker_required and route to AI/needs_review when doc looks opaque.
        heavy_doc = any((m or "").lower().startswith("image/") for m in email.attachment_mime_types) or any(
            (fn or "").lower().endswith(".pdf") for fn in email.attachment_filenames
        )
        worker_required = False

        final_category = deterministic.category
        final_conf = deterministic.confidence
        final_reasons = deterministic.evidence[:]
        final_driver_name = deterministic.driver_name

        # Confidence logic:
        high_t = float(thresholds.get("high", 0.90))
        medium_t = float(thresholds.get("medium", 0.72))

        worker_workflow_id = os.environ.get("WORKER_N8N_WORKFLOW_ID_EMAIL_DOC_INTEL", "").strip()
        worker_name = os.environ.get("WORKER_N8N_WORKER_NAME", "worker-rig-01").strip()

        # PDF/image + still uncategorized: try worker document intel before AI (permit vs other docs).
        pre_worker_uncategorized = bool(
            worker_workflow_id
            and heavy_doc
            and final_category == "uncategorized"
            and str(os.environ.get("EMAIL_SORTER_WORKER_BEFORE_AI_UNCATEGORIZED_PDF", "1")).strip().lower()
            in {"1", "true", "yes", "y"}
        )
        if pre_worker_uncategorized:
            cat, conf, reasons, driver_name, ok = _try_worker_document_intel(
                service=service,
                email=email,
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

        # Only invoke AI when not already high confidence (e.g. after doc intel).
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
            # Preserve deterministic driver name if AI didn't supply one.
            final_driver_name = driver_name or deterministic.driver_name

            if deterministic.category == "loads" and final_category != "loads":
                final_category = "loads"
                final_conf = max(final_conf, medium_t + 0.02)
                final_reasons = ["loads_channel_override"] + final_reasons

        # Worker offload hook (Phase 1 dry-run):
        # If a doc-heavy email is still not confidently classified, route to Needs Review.
        worker_required = bool(
            heavy_doc
            and final_conf < medium_t
            and final_category
            in {
                "permits",
                "loads",
                "driver_document",
                "uncategorized",
                "mydot",
                "progressive_insurance",
                "bank_statement",
            }
        )
        if worker_required and final_conf < medium_t:
            if worker_workflow_id:
                cat, conf, reasons, driver_name, ok = _try_worker_document_intel(
                    service=service,
                    email=email,
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

            # If still not confident enough after worker, route to Needs Review.
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

        # Driver child proposals for dry-run (report-only; never create).
        if proposed_child_label and would_create_child:
            summary["proposed_new_driver_child_labels"].add(proposed_child_label)

        # Apply mode: execute Gmail label mutations + optional archiving.
        if apply:
            # Resolve label IDs (create if missing).
            add_ids: list[str] = []
            for ln in proposed_labels:
                ln = (ln or "").strip()
                if not ln:
                    continue
                # In apply mode we must not create new driver child labels unless the
                # decision explicitly marked them as allowed.
                if proposed_child_label and ln == proposed_child_label and not would_create_child:
                    continue
                lid = str(get_or_create_label_id(ln))
                if lid:
                    add_ids.append(lid)

            remove_ids: list[str] = []
            if proposed_archive:
                # Gmail "archive" is removing the INBOX system label.
                remove_ids.append("INBOX")

            service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"addLabelIds": add_ids, "removeLabelIds": remove_ids},
            ).execute()

        # Needs review list: low-confidence OR explicitly needs_review.
        archive_executed = proposed_archive if apply else False
        summary["processed"] += 1
        summary["by_category"].setdefault(final_category, 0)
        summary["by_category"][final_category] += 1
        summary["by_band"][band] += 1
        if final_category == "needs_review" or proposed_labels == [needs_review_label]:
            summary["needs_review"] += 1
            if len(summary["emails_needs_review_all"]) < 250:
                summary["emails_needs_review_all"].append(
                    {
                        "message_id": message_id,
                        "sender": email.sender_email,
                        "sender_domain": email.sender_domain,
                        "subject": email.subject,
                        "deterministic_category": deterministic.category,
                        "confidence": final_conf,
                    }
                )
            if proposed_labels == [needs_review_label]:
                summary["emails_needs_review_only"].append(
                    {
                        "message_id": message_id,
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

        decision_source = "worker" if worker_used else ("ai" if ai_used else "deterministic")

        # Audit log entry (mandatory fields).
        audit_obj = {
            "generated_at": report_ts,
            "message_id": message_id,
            "thread_id": thread_id,
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
            "worker_offload_available": worker_offload_available,
            "decision_source": decision_source,
            "final_reasons": final_reasons,
            "matched_evidence": {
                "attachments": email.attachment_filenames,
                "sender_domain": email.sender_domain,
                "deterministic_reasons": deterministic.reasons,
                "final_reasons": final_reasons,
            },
            "proposed_labels": proposed_labels,
            "proposed_driver_child_label": proposed_child_label,
            "would_create_driver_child_label": would_create_child if dry_run else False,
            "proposed_archive": proposed_archive,
            "archive_executed": archive_executed,
            "dry_run": dry_run,
        }
        _audit_write(audit_f, audit_obj)

        # Phase D scaffold: propose deterministic rule keyword additions from high-confidence AI classifications.
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
                # Never crash mailbox processing due to learning proposals.
                pass

    audit_f.close()
    if learning_f is not None:
        learning_f.close()

    # Write markdown report.
    out_report_path = _AI_LAB_ROOT / "docs" / "EMAIL_BACKFILL_DRY_RUN_REPORT.md"
    out_report_path.parent.mkdir(parents=True, exist_ok=True)

    new_driver_list = sorted(list(summary["proposed_new_driver_child_labels"]))
    needs_review_only = summary["emails_needs_review_only"][:50]
    needs_review_all = summary["emails_needs_review_all"][:200]
    top_unmatched = sorted(summary["top_needs_review_unmatched"].items(), key=lambda kv: (-kv[1], kv[0]))[:25]

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
    parser = argparse.ArgumentParser(description="Integrated email sorter backfill (dry-run first).")
    parser.add_argument("--days", type=int, default=120, help="Look back N days.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate Gmail actions without changes.")
    parser.add_argument("--apply", action="store_true", help="Apply Gmail label actions (ARCHIVE is removed INBOX on high confidence).")
    parser.add_argument("--limit", type=int, default=100, help="Max emails to process.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    backfill_main(days=args.days, dry_run=args.dry_run, apply=args.apply, limit=args.limit)


if __name__ == "__main__":
    main()

