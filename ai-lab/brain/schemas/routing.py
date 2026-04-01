"""
Routing decision schema (Guru §21).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SourceKind = Literal[
    "artifact", "repo_search", "log", "config", "failure_record", "web", "time", "session"
]


@dataclass
class LocalTarget:
    kind: str
    path: str | None = None
    query: str | None = None
    priority: int = 1
    reason: str | None = None


@dataclass
class RoutingDecision:
    intent: str
    needs_local: bool = False
    needs_web: bool = False
    needs_time: bool = False
    needs_session: bool = True
    local_targets: list[LocalTarget] = field(default_factory=list)
    web_queries: list[str] = field(default_factory=list)
    session_targets: list[str] = field(default_factory=list)
    reason: str = ""
    confidence: float = 0.0
    answer_style_hint: str | None = None
