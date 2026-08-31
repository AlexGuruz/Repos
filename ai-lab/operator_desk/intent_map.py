"""Map natural-language operator asks to job_id / intent keys."""
from __future__ import annotations

import re

from .job_primer import load_job_manifest

# Phrase → intent_key (checked in order; first match wins)
_PHRASE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(unread|inbox|email|gmail|triage)\b", re.I), "email_digest"),
    (re.compile(r"\b(draft\s+reply|email\s+draft)\b", re.I), "email_draft"),
    (re.compile(r"\b(growflow|retail)\b.*\b(status|today|where|sales)\b", re.I), "growflow_status"),
    (re.compile(r"\b(where\s+are\s+we|retail\s+today|sales\s+today)\b", re.I), "growflow_status"),
    (re.compile(r"\b(capital|buy\s*plan|allocation\s+pool)\b", re.I), "growflow_capital"),
    (re.compile(r"\b(consignment|net\s*terms|vendor\s+pull)\b", re.I), "growflow_consignment"),
    (re.compile(r"\b(eod|forecast|projection)\b", re.I), "growflow_projection"),
    (re.compile(r"\b(company\s*bi|bi\s+report|sheets\s+transactions)\b", re.I), "growflow_bi"),
    (re.compile(r"\b(growflow\s+catalog|read\s+surfaces)\b", re.I), "growflow_catalog"),
    (re.compile(r"\b(pending\s+approvals?|approval\s+queue)\b", re.I), "pending_approvals"),
    (re.compile(r"\b(machine|restart|run\s+approved)\b", re.I), "machine_status"),
    (re.compile(r"\b(repos?|projects?\s+in\s+repos|repo\s+map|what\s+projects)\b", re.I), "repo_map"),
]


def resolve_intent_key(message: str) -> str | None:
    text = (message or "").strip()
    if not text:
        return None
    for pattern, intent_key in _PHRASE_RULES:
        if pattern.search(text):
            return intent_key
    return None


def resolve_job_id_for_intent(intent_key: str) -> str | None:
    for entry in load_job_manifest().values():
        if intent_key in entry.intent_keys:
            return entry.job_id
    return None


def resolve_job_id_for_message(message: str) -> str | None:
    intent = resolve_intent_key(message)
    if not intent:
        return None
    return resolve_job_id_for_intent(intent)
