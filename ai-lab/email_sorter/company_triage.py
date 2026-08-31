from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_AI_LAB_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_RULES_PATH = _AI_LAB_ROOT / "email_sorter" / "config" / "company_rules.yaml"
_DEFAULT_LABELS_PATH = _AI_LAB_ROOT / "email_sorter" / "config" / "company_labels.yaml"

COMPANY_CATEGORIES = (
    "hot_urgent",
    "legal_compliance",
    "bills_invoices",
    "investors_finance",
    "licenses_executive",
    "retail_operations",
    "needs_reply",
    "summary_worthy",
    "needs_review",
)


@dataclass(frozen=True)
class EmailMessage:
    account_id: str
    message_id: str
    thread_id: str
    from_header: str
    subject: str
    snippet: str
    body: str
    sender_email: str = ""
    sender_domain: str = ""


@dataclass(frozen=True)
class TriageResult:
    category: str
    confidence: float
    reasons: tuple[str, ...]
    gmail_label: str


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _normalize_ws(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _parse_sender(from_header: str) -> tuple[str, str]:
    match = re.search(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", from_header or "", flags=re.I)
    email = match.group(1).strip().lower() if match else (from_header or "").strip().lower()
    domain = email.split("@", 1)[1] if "@" in email else ""
    return email, domain


def _contains_keyword(text: str, keywords: list[str]) -> str | None:
    hay = (text or "").lower()
    for keyword in keywords:
        kw = (keyword or "").strip().lower()
        if not kw:
            continue
        if kw in hay:
            return kw
    return None


def _domain_matches(domain: str, patterns: list[str]) -> str | None:
    d = (domain or "").lower()
    for pattern in patterns:
        p = (pattern or "").strip().lower()
        if not p:
            continue
        if d == p or d.endswith("." + p) or p in d:
            return p
    return None


def _signal_block_match(
    *,
    email: EmailMessage,
    block: dict[str, Any],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    sender_emails = block.get("sender_emails") or []
    if isinstance(sender_emails, list):
        for addr in sender_emails:
            if str(addr).strip().lower() == email.sender_email:
                reasons.append(f"sender_email:{addr}")
                return True, reasons

    sender_domains = block.get("sender_domains") or []
    if isinstance(sender_domains, list):
        hit = _domain_matches(email.sender_domain, [str(x) for x in sender_domains])
        if hit:
            reasons.append(f"sender_domain:{hit}")
            return True, reasons

    subject_keywords = block.get("subject_keywords") or []
    if isinstance(subject_keywords, list):
        hit = _contains_keyword(email.subject, [str(x) for x in subject_keywords])
        if hit:
            reasons.append(f"subject:{hit}")
            return True, reasons

    body_keywords = block.get("body_keywords") or []
    if isinstance(body_keywords, list):
        combined = f"{email.snippet}\n{email.body}"
        hit = _contains_keyword(combined, [str(x) for x in body_keywords])
        if hit:
            reasons.append(f"body:{hit}")
            return True, reasons

    attachment_keywords = block.get("attachment_filename_keywords") or []
    if isinstance(attachment_keywords, list) and attachment_keywords:
        # Command center currently passes empty attachment list; keep hook for future use.
        return False, reasons

    return False, reasons


def load_company_label_map(labels_path: Path | None = None) -> dict[str, str]:
    data = _load_yaml(labels_path or _DEFAULT_LABELS_PATH)
    mapping = data.get("category_label_map") or {}
    if not isinstance(mapping, dict):
        return {}
    return {str(k): str(v) for k, v in mapping.items() if str(k).strip() and str(v).strip()}


def classify_company_email(
    email: EmailMessage,
    *,
    rules_path: Path | None = None,
    labels_path: Path | None = None,
) -> TriageResult:
    rules = _load_yaml(rules_path or _DEFAULT_RULES_PATH)
    label_map = load_company_label_map(labels_path=labels_path)
    priority = rules.get("priority_order") or list(COMPANY_CATEGORIES)
    boosts = rules.get("account_category_boosts") or {}
    account_boosts = boosts.get(email.account_id) or []

    sender_email, sender_domain = _parse_sender(email.from_header)
    enriched = EmailMessage(
        account_id=email.account_id,
        message_id=email.message_id,
        thread_id=email.thread_id,
        from_header=email.from_header,
        subject=_normalize_ws(email.subject),
        snippet=_normalize_ws(email.snippet),
        body=_normalize_ws(email.body),
        sender_email=sender_email or email.sender_email,
        sender_domain=sender_domain or email.sender_domain,
    )

    for category in priority:
        cat = str(category).strip()
        if cat not in COMPANY_CATEGORIES:
            continue
        block = rules.get(f"{cat}_signals") or {}
        if not isinstance(block, dict):
            continue
        matched, reasons = _signal_block_match(email=enriched, block=block)
        if not matched:
            continue
        confidence = 0.82
        if cat in account_boosts:
            confidence = min(0.95, confidence + 0.08)
            reasons = [*reasons, f"account_boost:{email.account_id}"]
        gmail_label = label_map.get(cat, label_map.get("needs_review", "Needs Review"))
        return TriageResult(
            category=cat,
            confidence=confidence,
            reasons=tuple(reasons),
            gmail_label=gmail_label,
        )

    gmail_label = label_map.get("needs_review", "Needs Review")
    return TriageResult(
        category="needs_review",
        confidence=0.35,
        reasons=("no_rule_match",),
        gmail_label=gmail_label,
    )
