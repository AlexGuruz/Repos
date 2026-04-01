"""
Source selection for Phase-7: freshness detection and source router.
Determines when to use local only, web, or both (Tier 1/2/3).
"""
from __future__ import annotations

# Explicit freshness
_FRESHNESS_WORDS = (
    "today", "now", "current", "latest", "recent", "as of", "this week",
)
# External lookup
_EXTERNAL_WORDS = (
    "weather", "price", "docs", "api", "release", "broker", "law", "regulation",
    "availability", "news", "pricing", "vendor",
)
# Verification phrases (substrings)
_VERIFICATION_PHRASES = (
    "is this still", "has this changed", "is this outdated", "compare with current",
)


def detect_freshness(message: str) -> bool:
    """
    Return True when the message suggests current or external information is needed.
    Uses explicit freshness, external lookup, and verification phrase triggers.
    """
    if not message:
        return False
    msg = message.strip().lower()
    for w in _FRESHNESS_WORDS:
        if w in msg:
            return True
    for w in _EXTERNAL_WORDS:
        if w in msg:
            return True
    for phrase in _VERIFICATION_PHRASES:
        if phrase in msg:
            return True
    return False


def select_sources(
    intent: str,
    needs_web: bool,
    session_context: dict | None = None,
) -> str:
    """
    Determine which evidence sources to gather.
    Returns one of: "local", "web", "local+web", "web+time", "local+time".
    Implements Tier 1 (local), Tier 2 (local+web), Tier 3 (web only).
    """
    session_context = session_context or {}
    # Tier 1 – clearly internal
    if intent in ("run", "run_agent", "scan_results", "approval", "execute_proposal", "repo_search"):
        if needs_web:
            return "local+web"
        return "local"
    # Tier 3 – purely external (answer intent + strong web triggers)
    if intent == "answer" and needs_web:
        msg = (session_context.get("message") or "").lower()
        # Weather uses Open-Meteo in the main router (no Tavily/Serper)
        if "weather" in msg and not any(w in msg for w in ("repo", "scan", "script", "config", "our", "my ")):
            return "local+time"
        # News, price alone -> web only
        if any(w in msg for w in ("news", "price", "pricing", "vendor")):
            if not any(w in msg for w in ("repo", "scan", "script", "config", "our", "my ")):
                return "web"
        return "local+web"
    if intent == "answer":
        return "local+time" if needs_web else "local"
    return "local"
