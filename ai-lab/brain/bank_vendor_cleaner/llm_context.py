"""
Bank Vendor Cleaner — LLM system-prompt context for Command Center chat.

Injected when the user is discussing transaction cleaning, aliases, or vendor lookup.
The model is a reasoning helper only; deterministic code owns sheet writes.
"""
from __future__ import annotations

from pathlib import Path

from brain.bank_vendor_cleaner.paths import (
    memory_buckets_path,
    qwen_operating_prompt_path,
)

BANK_VENDOR_ACTIVE_TOPIC = "bank_vendor_cleaner"

_BANK_VENDOR_PHRASES = (
    "bank vendor",
    "vendor cleaner",
    "transaction cleaner",
    "clean sheet labels",
    "cleaned transactions",
    "canonical label",
    "memory alias",
    "alias map",
    "vendor lookup",
    "unknown merchant",
    "city/state",
    "city state column",
    "label pipeline",
    "sheet_label_pipeline",
    "murphy7440",
    "wm supercenter",
    "backfill cleaned",
    "promote alias",
    "rejected alias",
)

_FILE_CACHE: dict[str, tuple[float | None, str]] = {}


def _read_cached(path: Path, *, max_chars: int | None = None) -> str:
    key = str(path.resolve())
    mtime: float | None = None
    try:
        mtime = path.stat().st_mtime if path.is_file() else None
    except OSError:
        mtime = None
    sentinel = mtime if mtime is not None else -1.0
    cached = _FILE_CACHE.get(key)
    if cached and cached[0] == sentinel:
        text = cached[1]
    else:
        if not path.is_file():
            _FILE_CACHE[key] = (sentinel, "")
            return ""
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            _FILE_CACHE[key] = (sentinel, "")
            return ""
        _FILE_CACHE[key] = (sentinel, text)
    if max_chars is not None and len(text) > max_chars:
        return text[:max_chars] + "\n\n_(truncated for prompt budget)_"
    return text


def is_bank_vendor_context(
    message: str,
    *,
    session_id: str | None = None,
    intent: str | None = None,
    params: dict | None = None,
) -> bool:
    """True when chat should load Bank Vendor Cleaner runtime policy into the system prompt."""
    if intent == "bank_vendor_qa":
        return True
    if params:
        tool = str(params.get("tool_hint") or "")
        if "bank_vendor" in tool:
            return True
    msg = (message or "").strip().lower()
    if any(phrase in msg for phrase in _BANK_VENDOR_PHRASES):
        return True
    if session_id:
        try:
            from brain import session_state

            if session_state.peek_active_topic(session_id) == BANK_VENDOR_ACTIVE_TOPIC:
                return True
        except Exception:
            pass
    return False


def build_llm_system_addon(*, max_operating_prompt_chars: int = 14000) -> str:
    """Qwen operating prompt + memory index for orchestrator system-prompt injection."""
    parts: list[str] = []
    operating = _read_cached(qwen_operating_prompt_path(), max_chars=max_operating_prompt_chars)
    if operating:
        parts.append(operating)
    buckets = _read_cached(memory_buckets_path(), max_chars=2000)
    if buckets:
        parts.extend(
            [
                "",
                "### Local memory files (read via pipeline; suggest edits for approval only)",
                "```yaml",
                buckets,
                "```",
            ]
        )
    if not parts:
        return ""
    return "\n".join(parts).strip()


def append_to_system_prompt(
    system_content: str,
    message: str,
    *,
    session_id: str,
    intent: str,
    params: dict | None = None,
) -> str:
    """Append bank vendor policy to the orchestrator system prompt when context matches."""
    if not is_bank_vendor_context(
        message,
        session_id=session_id,
        intent=intent,
        params=params or {},
    ):
        return system_content
    addon = build_llm_system_addon()
    if not addon:
        return system_content
    return system_content + "\n\n" + addon
