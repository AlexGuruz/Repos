"""Typed Operator Desk result models (contracts v1)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Freshness = Literal["fresh", "stale_but_usable", "degraded", "unavailable"]


@dataclass
class ResultEnvelope:
    ok: bool
    source: str
    freshness: Freshness
    generated_at: str | None = None
    warnings: list[str] = field(default_factory=list)
    error_code: str | None = None
    degraded: bool = False
    approval_required: bool = False
    approval_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JobPrimerBundle(ResultEnvelope):
    job_id: str = ""
    title: str = ""
    primer_markdown: str = ""
    primer_path: str = ""
    tool_ids: list[str] = field(default_factory=list)
    max_chars_applied: bool = False


@dataclass
class EmailMessageView:
    id: str
    thread_id: str
    from_redacted: str
    subject: str
    classification: str
    snippet_redacted: str


@dataclass
class EmailAccountDigest:
    account_id: str
    email: str
    messages: list[EmailMessageView] = field(default_factory=list)


@dataclass
class EmailDigestResult(ResultEnvelope):
    accounts: list[EmailAccountDigest] = field(default_factory=list)
    total_unread: int = 0
    cache_hit: bool = False


@dataclass
class GrowflowStatusResult(ResultEnvelope):
    summary: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    known_blockers: list[str] = field(default_factory=list)


@dataclass
class ApprovalSubmissionResult(ResultEnvelope):
    tool_name: str = ""
    status: str = "pending"


@dataclass
class MachinePendingItem:
    approval_id: str
    action_type: str
    reason: str
    risk_level: str
    created_at: str | None = None
    tool_name: str | None = None


@dataclass
class MachinePendingResult(ResultEnvelope):
    items: list[MachinePendingItem] = field(default_factory=list)


@dataclass
class RepoMapEntry:
    repo_id: str
    path: str
    summary: str


@dataclass
class RepoMapResult(ResultEnvelope):
    repos: list[RepoMapEntry] = field(default_factory=list)
    query: str | None = None
