"""
Web query builder (PDR Phase 2.9). Builds search queries from message + session.
Rules: include entities, expand vague phrasing, add freshness terms when needed.
"""
from __future__ import annotations


def build_web_query(message: str, session: dict | None = None) -> str:
    """
    Build a web search query from the user message and optional session context.
    Expands vague queries with "current" / "latest" when appropriate.
    """
    session = session or {}
    msg = (message or "").strip()
    if not msg:
        return ""

    # Preserve meaningful words; drop very short
    words = [w for w in msg.split() if len(w) > 2][:8]
    base = " ".join(words) if words else msg[:80]

    # Add freshness terms for common intents
    lower = base.lower()
    if any(x in lower for x in ("weather", "today", "current", "latest", "now")):
        if "current" not in lower and "latest" not in lower:
            base = f"{base} current" if base else "current"
    if any(x in lower for x in ("docs", "api", "release", "version")):
        if "latest" not in lower:
            base = f"{base} latest" if base else "latest"

    # Optional: inject entities from session (e.g. active_topic, recent_entities)
    entities = session.get("recent_entities") or []
    if entities and len(base) < 60:
        extra = " ".join(entities[:2])
        if extra and extra.lower() not in base.lower():
            base = f"{base} {extra}".strip()

    return base[:120]
