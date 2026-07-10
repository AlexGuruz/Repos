"""
Hybrid keyword / alias / intent snapshot selection for prepared context.

Deterministic only (no embeddings). Target: sub-millisecond typical runtime.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
_ALL_TYPES: tuple[str, ...] = (
    "system_snapshot",
    "repo_pulse",
    "project_agenda",
    "personal_ops_snapshot",
    "growflow_snapshot",
    "worker_snapshot",
)

# (weight, phrase) — phrase matched with `if phrase in message_lower`
_SYSTEM_HINTS: tuple[tuple[float, str], ...] = (
    (0.42, "systems are active"),
    (0.42, "what systems"),
    (0.38, "what is running"),
    (0.38, "what's running"),
    (0.4, "anything broken"),
    (0.36, "something broken"),
    (0.35, "status of the lab"),
    (0.38, "lab status"),
    (0.36, "command center healthy"),
    (0.34, "command center health"),
    (0.36, "services online"),
    (0.34, "services are online"),
    (0.32, "what services"),
    (0.3, "system health"),
    (0.28, "unhealthy"),
    (0.28, "degraded"),
    (0.26, "big picture"),
    (0.22, "how are things"),
)

_REPO_HINTS: tuple[tuple[float, str], ...] = (
    (0.45, "explain repo documentation status"),
    (0.42, "repo documentation"),
    (0.4, "docs are stale"),
    (0.38, "documentation status"),
    (0.38, "docs need cleanup"),
    (0.36, "which repos need cleanup"),
    (0.4, "summarize repo status"),
    (0.38, "repo status"),
    (0.36, "summarize current repo status"),
    (0.42, "what changed recently"),
    (0.34, "what changed"),
    (0.32, "recent changes"),
    (0.34, "stale readme"),
    (0.32, "readme stale"),
    (0.3, "codebase needs attention"),
    (0.32, "repos have todos"),
    (0.3, "repo todos"),
    (0.28, "cleanup"),
)

_AGENDA_HINTS: tuple[tuple[float, str], ...] = (
    (0.45, "open project agenda"),
    (0.44, "project agenda"),
    (0.4, "what is next"),
    (0.38, "what's next"),
    (0.38, "what are my next actions"),
    (0.36, "next actions"),
    (0.36, "what should i work on today"),
    (0.34, "what to work on today"),
    (0.38, "what is blocked"),
    (0.36, "what's blocked"),
    (0.34, "blocked on"),
    (0.32, "priorities are active"),
    (0.32, "current priorities"),
    (0.3, "daily plan"),
    (0.28, "backlog"),
)

_PERSONAL_HINTS: tuple[tuple[float, str], ...] = (
    (0.45, "what should i focus on today"),
    (0.42, "focus on today"),
    (0.4, "plan my day"),
    (0.42, "what is on my calendar"),
    (0.4, "on my calendar"),
    (0.36, "daily assistant"),
    (0.34, "check-in"),
    (0.34, "what did i miss"),
    (0.36, "needs my attention today"),
    (0.38, "personal ops"),
    (0.34, "daily digest"),
    (0.32, "reminder"),
    (0.3, "which repos are stale"),
    (0.3, "repos are stale"),
)

_WORKER_HINTS: tuple[tuple[float, str], ...] = (
    (0.48, "worker status"),
    (0.46, "is the worker online"),
    (0.44, "worker online"),
    (0.42, "ollama status"),
    (0.42, "is ollama up"),
    (0.42, "ollama up"),
    (0.42, "n8n status"),
    (0.4, "is n8n"),
    (0.38, "offload status"),
    (0.4, "can the worker run"),
    (0.36, "worker assistant"),
    (0.34, "tunnel status"),
)

_GROWFLOW_HINTS: tuple[tuple[float, str], ...] = (
    (0.5, "growflow status"),
    (0.48, "growflow updates"),
    (0.44, "recent growflow automation changes"),
    (0.46, "grow flow"),
    (0.42, "par system"),
    (0.4, "transfer receipt"),
    (0.38, "dashboard export"),
    (0.38, "projection dashboard"),
    (0.36, "business automation status"),
    (0.36, "inventory automation status"),
    (0.34, "landed cost"),
    (0.32, "company bi"),
)

_CHANGE_MARKERS = (
    "changed",
    "change",
    "recent",
    "update",
    "updates",
    "delta",
    "new",
)

_REPO_CODE_DOC_MARKERS = (
    "repo",
    "repos",
    "code",
    "docs",
    "documentation",
    "readme",
    "cleanup",
    "commit",
)

# Require at least one of these substrings for growflow when generic "inventory" appears alone.
_GROWFLOW_ANCHOR = (
    "growflow",
    "grow flow",
    "par ",
    "par/",
    "transfer receipt",
    "receipt",
    "business automation",
    "inventory automation",
    "dashboard export",
    "dispensary",
    "projection",
    "company bi",
    "landed cost",
)

_BROAD_LAB_MARKERS = (
    "status of the lab",
    "anything broken",
    "lab overview",
    "overall status",
    "how is the lab",
    "how's the lab",
)

_TIME_SENSITIVE = (
    "now",
    "current",
    "today",
    "status",
    "online",
    "healthy",
    "running",
    "recent",
    "still",
    "right now",
)

_GENERIC_KNOWLEDGE = (
    "who won",
    "capital of",
    "translate ",
    "define ",
    "what is photosynthesis",
)


@dataclass
class SnapshotSelection:
    snapshot_types: list[str]
    scores: dict[str, float]
    reasons: dict[str, list[str]]
    rejected_candidates: list[dict[str, str]]
    broad_prompt: bool
    time_sensitive: bool
    selection_ms: float


def _score_hints(m: str, hints: tuple[tuple[float, str], ...], bucket: str, acc: dict[str, float], reasons: dict[str, list[str]]) -> None:
    for w, phrase in hints:
        if phrase in m:
            acc[bucket] = max(acc.get(bucket, 0.0), w)
            reasons.setdefault(bucket, []).append(f"match:{phrase}")


def select_snapshots_for_message(message: str, intent: str | None = None) -> SnapshotSelection:
    t0 = time.perf_counter()
    m = (message or "").strip().lower()
    scores: dict[str, float] = {k: 0.0 for k in _ALL_TYPES}
    reasons: dict[str, list[str]] = {k: [] for k in _ALL_TYPES}
    rejected: list[dict[str, str]] = []

    _score_hints(m, _SYSTEM_HINTS, "system_snapshot", scores, reasons)
    _score_hints(m, _REPO_HINTS, "repo_pulse", scores, reasons)
    _score_hints(m, _AGENDA_HINTS, "project_agenda", scores, reasons)
    _score_hints(m, _PERSONAL_HINTS, "personal_ops_snapshot", scores, reasons)
    _score_hints(m, _WORKER_HINTS, "worker_snapshot", scores, reasons)
    _score_hints(m, _GROWFLOW_HINTS, "growflow_snapshot", scores, reasons)

    # Intent nudges (deterministic, from router / orchestrator)
    if intent == "company_bi":
        scores["growflow_snapshot"] = max(scores["growflow_snapshot"], 0.48)
        reasons["growflow_snapshot"].append("intent:company_bi")
    if intent == "ops_overview":
        scores["system_snapshot"] = max(scores["system_snapshot"], 0.35)
        reasons["system_snapshot"].append("intent:ops_overview")
    if intent == "worker_health":
        scores["worker_snapshot"] = max(scores["worker_snapshot"], 0.52)
        reasons["worker_snapshot"].append("intent:worker_health")

    # Growflow recent-change phrasing should prefer growflow_snapshot.
    growflow_mentioned = ("growflow" in m) or ("grow flow" in m)
    change_mentioned = any(c in m for c in _CHANGE_MARKERS)
    if growflow_mentioned and change_mentioned:
        scores["growflow_snapshot"] = max(scores["growflow_snapshot"], 0.54)
        reasons["growflow_snapshot"].append("growflow_change_boost")
        # Keep repo_pulse only when the prompt explicitly asks about repo/code/doc changes.
        if not any(k in m for k in _REPO_CODE_DOC_MARKERS):
            if scores.get("repo_pulse", 0.0) > 0:
                rejected.append({"snapshot_type": "repo_pulse", "reason": "growflow_change_without_repo_code_docs"})
            scores["repo_pulse"] = 0.0
            reasons["repo_pulse"] = []

    # Repo documentation / cleanup: keep legacy pairing with system_snapshot without firing the broad trio.
    doc_repo_q = any(x in m for x in ("documentation", "docs", "readme", "cleanup")) and scores.get("repo_pulse", 0) >= 0.25
    if doc_repo_q:
        scores["system_snapshot"] = max(scores["system_snapshot"], 0.24)
        reasons.setdefault("system_snapshot", []).append("doc_repo_pairing")

    # Growflow: block generic "inventory" without business/Growflow anchors.
    inv_word = "inventory" in m or " stock " in m or m.rstrip().endswith("stock")
    if inv_word and scores.get("growflow_snapshot", 0) > 0:
        if not any(a in m for a in _GROWFLOW_ANCHOR):
            rejected.append({"snapshot_type": "growflow_snapshot", "reason": "inventory_like_without_growflow_anchor"})
            scores["growflow_snapshot"] = 0.0
            reasons["growflow_snapshot"] = []

    # Personal ops: require planning/calendar/focus/daily flavor if message is only generic "work".
    if scores.get("personal_ops_snapshot", 0) > 0:
        personal_markers = ("today", "calendar", "focus", "plan", "daily", "personal", "reminder", "digest", "attention", "miss", "stale")
        if " work " in m or m.startswith("work ") or m.endswith(" work"):
            if not any(p in m for p in personal_markers):
                rejected.append({"snapshot_type": "personal_ops_snapshot", "reason": "generic_work_without_planning_markers"})
                scores["personal_ops_snapshot"] = 0.0
                reasons["personal_ops_snapshot"] = []

    # Worker snapshot: require explicit worker/automation cues (avoid "status" alone).
    if scores.get("worker_snapshot", 0) > 0:
        worker_anchor = ("worker", "ollama", "n8n", "offload", "tunnel", "assistant")
        if not any(a in m for a in worker_anchor):
            rejected.append({"snapshot_type": "worker_snapshot", "reason": "no_worker_anchor"})
            scores["worker_snapshot"] = 0.0
            reasons["worker_snapshot"] = []

    # Broad lab/status prompts: combine core trio when not domain-specific.
    domain_high = max(
        scores.get("growflow_snapshot", 0),
        scores.get("personal_ops_snapshot", 0),
        scores.get("worker_snapshot", 0),
    ) >= 0.42
    doc_focus = any(x in m for x in ("documentation", "docs", "readme", "cleanup", "repo documentation"))
    broad_prompt = (
        any(b in m for b in _BROAD_LAB_MARKERS)
        or (
            ("overview" in m or "summary" in m or "status" in m)
            and "growflow" not in m
            and "worker" not in m
            and "calendar" not in m
            and not domain_high
            and not doc_focus
        )
    )
    if broad_prompt and not domain_high:
        for b in ("system_snapshot", "repo_pulse", "project_agenda"):
            if scores[b] < 0.22:
                scores[b] = 0.22
                reasons[b].append("broad_prompt_trio_boost")

    # Unrelated general knowledge → clear weak accidental hits
    if any(g in m for g in _GENERIC_KNOWLEDGE):
        rejected.append({"snapshot_type": "*", "reason": "generic_knowledge_query"})
        scores = {k: 0.0 for k in _ALL_TYPES}
        reasons = {k: [] for k in _ALL_TYPES}

    time_sensitive = any(t in m for t in _TIME_SENSITIVE)

    MIN_SCORE = 0.19
    ordered = sorted(_ALL_TYPES, key=lambda k: scores.get(k, 0.0), reverse=True)
    picked: list[str] = []
    for k in ordered:
        if scores.get(k, 0.0) >= MIN_SCORE:
            picked.append(k)
    # Cap to avoid huge replies
    picked = picked[:4]

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 4)
    return SnapshotSelection(
        snapshot_types=picked,
        scores={k: round(scores.get(k, 0.0), 3) for k in _ALL_TYPES},
        reasons={k: v for k, v in reasons.items() if v},
        rejected_candidates=rejected,
        broad_prompt=broad_prompt,
        time_sensitive=time_sensitive,
        selection_ms=elapsed_ms,
    )
