"""
Fast-path routing hints for intent=answer (no new architecture).

Keeps source_router readable: return overrides before generic freshness→web heuristics.
"""
from __future__ import annotations

from dataclasses import dataclass

from brain.schemas.routing import LocalTarget


@dataclass(frozen=True)
class AnswerFastPath:
    """When matched, caller should apply these and skip remaining answer-branch heuristics."""

    needs_local: bool
    needs_web: bool
    local_targets: tuple[LocalTarget, ...]
    reason: str
    answer_style_hint: str


def _ai_lab_readme_path() -> str | None:
    try:
        from pathlib import Path

        p = Path(__file__).resolve().parents[2] / "README.md"
        return str(p) if p.is_file() else None
    except Exception:
        return None


def match_answer_fast_path(message: str) -> AnswerFastPath | None:
    """
    Deterministic fast paths for common chat turns.

    Goals:
    - Planning + "today" must not auto-open paid web search.
    - Lab/workspace summary must pull ops registry (+ README) without waiting on web.
    """
    msg = (message or "").strip().lower()
    if not msg:
        return None

    planning_markers = (
        "what should i work on",
        "what to work on",
        "what do i work on",
        "where should i focus",
        "prioritize",
        "prioritise",
        "what's my priority",
        "whats my priority",
        "backlog",
    )
    if any(p in msg for p in planning_markers):
        return AnswerFastPath(
            needs_local=True,
            needs_web=False,
            local_targets=(
                LocalTarget(
                    kind="ops_registry",
                    priority=1,
                    reason="Planning / prioritization question — load ops registry (no web).",
                ),
            ),
            reason="Planning question: ops registry + session time only; freshness keywords ignored for web.",
            answer_style_hint="direct_status",
        )

    summary_markers = (
        "summarize",
        "summary",
        "current state",
        "high level",
        "overview of",
        "what exists",
        "what's built",
        "whats built",
        "built out",
    )
    lab_markers = (
        "ai-lab",
        "ai lab",
        "command center",
        "command-center",
        "orchestrator",
        "my stack",
        "local ai",
    )
    if any(s in msg for s in summary_markers) and any(l in msg for l in lab_markers):
        targets: list[LocalTarget] = [
            LocalTarget(
                kind="ops_registry",
                priority=1,
                reason="Lab / workspace summary — load ops registry.",
            ),
        ]
        readme = _ai_lab_readme_path()
        if readme:
            targets.append(
                LocalTarget(
                    kind="artifact",
                    path=readme,
                    priority=2,
                    reason="ai-lab README for orientation.",
                )
            )
        return AnswerFastPath(
            needs_local=True,
            needs_web=False,
            local_targets=tuple(targets),
            reason="Lab/workspace summary: ops registry + README (no web).",
            answer_style_hint="summary_from_artifact",
        )

    growflow_markers = ("growflow", "grow flow")
    change_markers = ("change", "changed", "recent", "delta", "what's new", "whats new", "since")
    if any(g in msg for g in growflow_markers) and any(c in msg for c in change_markers):
        from pathlib import Path

        p = Path(__file__).resolve().parents[2].parent / "Growflow" / "README.md"
        if p.is_file():
            return AnswerFastPath(
                needs_local=True,
                needs_web=False,
                local_targets=(
                    LocalTarget(
                        kind="artifact",
                        path=str(p),
                        priority=1,
                        reason="Growflow orientation from repo README (no web).",
                    ),
                ),
                reason="Growflow change/context question — README snapshot (use git log for exact deltas).",
                answer_style_hint="summary_from_artifact",
            )

    doc_markers = ("documentation", "doc status", "docs status", "doc health")
    repo_markers = ("repo", "repos", "repository")
    if any(d in msg for d in doc_markers) and any(r in msg for r in repo_markers):
        readme = _ai_lab_readme_path()
        if readme:
            return AnswerFastPath(
                needs_local=True,
                needs_web=False,
                local_targets=(
                    LocalTarget(
                        kind="artifact",
                        path=readme,
                        priority=1,
                        reason="Repo/documentation orientation from ai-lab README (no web).",
                    ),
                ),
                reason="Documentation status in repo context — README (no web).",
                answer_style_hint="summary_from_artifact",
            )

    return None
