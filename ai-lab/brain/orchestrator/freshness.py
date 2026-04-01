"""
Freshness detection (Guru §21). Determines if the message needs current external info and/or time context.

Uses whole-word token matching for short triggers so substrings like "now" in "knowledge" or "api" in "rapid"
do not spuriously enable web search (which made casual chat feel "stuck" waiting on Tavily + LLM).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Single tokens: must appear as their own word (see _message_tokens).
EXPLICIT_RECENCY_TOKENS = {
    "today", "now", "current", "latest", "recent", "recently",
}

# Multi-word phrases: substring match on normalized message.
EXPLICIT_RECENCY_PHRASES = ("as of", "this week", "this month")

# Tokens that imply external / time-sensitive lookup when they stand alone as words.
EXTERNAL_CURRENT_TOKENS = {
    "weather", "docs", "api", "release", "version", "price", "broker",
    "law", "regulation", "availability", "patch", "news", "pricing", "vendor",
}

COMPARISON_CURRENT = (
    "still valid", "still current", "outdated", "changed", "compare with current", "as of now",
)

# Substrings of EXPLICIT_RECENCY_TOKENS that should turn on time context (matches prior behavior).
_TIME_RECENCY_TOKENS = frozenset({"today", "now", "current", "latest"})
_TIME_RECENCY_PHRASES = frozenset({"this week", "this month"})


def _message_tokens(msg: str) -> set[str]:
    """Lowercase alphanumeric tokens (no substring matches inside longer words)."""
    return set(re.findall(r"[a-z0-9]+", msg))


@dataclass
class FreshnessResult:
    freshness_needed: bool
    needs_time: bool
    confidence: float
    triggers: list[str]


def detect_freshness(message: str) -> FreshnessResult:
    """
    Return FreshnessResult indicating whether current external info and/or time is needed.
    """
    if not message:
        return FreshnessResult(False, False, 0.0, [])
    msg = message.strip().lower()
    triggers: list[str] = []
    needs_time = False
    tokens = _message_tokens(msg)
    for w in EXPLICIT_RECENCY_TOKENS:
        if w in tokens:
            triggers.append(w)
            if w in _TIME_RECENCY_TOKENS:
                needs_time = True
    for phrase in EXPLICIT_RECENCY_PHRASES:
        if phrase in msg:
            triggers.append(phrase)
            if phrase in _TIME_RECENCY_PHRASES:
                needs_time = True
    for w in EXTERNAL_CURRENT_TOKENS:
        if w in tokens:
            triggers.append(w)
    for phrase in COMPARISON_CURRENT:
        if phrase in msg:
            triggers.append(phrase)
    freshness_needed = len(triggers) > 0
    confidence = min(0.99, 0.5 + 0.1 * len(triggers)) if freshness_needed else 0.0
    return FreshnessResult(
        freshness_needed=freshness_needed,
        needs_time=needs_time,
        confidence=confidence,
        triggers=triggers,
    )
