"""
Planning data model for live work orchestration (Phase 9 + Phase 10 ClickUp alignment).

Serializable dataclasses — no side effects.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


StatusT = Literal["open", "in_progress", "done", "blocked", "cancelled", "unknown"]
BlockerSeverityT = Literal["low", "medium", "high"]
CommQueueTypeT = Literal["clarification", "followup", "system_message"]
ActionStateT = Literal["preview", "queued", "approved", "executed"]
ProgressSourceT = Literal["repo", "manual", "clickup", "system"]


@dataclass
class WorkDemand:
    id: str
    source: str
    confidence: float
    observed_at: str
    created_at: str
    notes: str
    evidence: list[str] = field(default_factory=list)
    status: StatusT = "open"
    title: str = ""
    project_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TimeConstraint:
    id: str
    source: str
    confidence: float
    observed_at: str
    created_at: str
    notes: str
    evidence: list[str] = field(default_factory=list)
    status: StatusT = "open"
    label: str = ""
    window_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlanningBlock:
    id: str
    source: str
    confidence: float
    observed_at: str
    created_at: str
    notes: str
    evidence: list[str] = field(default_factory=list)
    status: StatusT = "open"
    block_type: str = ""
    start_hint: str = ""
    end_hint: str = ""
    linked_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlannedTask:
    id: str
    source: str
    confidence: float
    observed_at: str
    created_at: str
    notes: str
    evidence: list[str] = field(default_factory=list)
    status: StatusT = "open"
    title: str = ""
    bucket: str = ""
    clickup_list: str = ""
    clickup_task_id: str | None = None
    category: str = ""
    action_state: ActionStateT = "preview"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Blocker:
    id: str
    source: str
    confidence: float
    observed_at: str
    created_at: str
    notes: str
    evidence: list[str] = field(default_factory=list)
    status: StatusT = "open"
    severity: BlockerSeverityT = "medium"
    route_hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProgressEvent:
    id: str
    source: str
    confidence: float
    observed_at: str
    created_at: str
    notes: str
    evidence: list[str] = field(default_factory=list)
    status: StatusT = "done"
    metric: str = ""
    source_type: ProgressSourceT = "repo"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CommunicationQueueItem:
    id: str
    source: str
    confidence: float
    observed_at: str
    created_at: str
    notes: str
    evidence: list[str] = field(default_factory=list)
    status: StatusT = "open"
    clickup_list: str = ""
    comm_type: CommQueueTypeT = "clarification"
    payload_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["type"] = d.pop("comm_type")
        return d


@dataclass
class PlanRevision:
    id: str
    source: str
    confidence: float
    observed_at: str
    created_at: str
    notes: str
    evidence: list[str] = field(default_factory=list)
    status: StatusT = "open"
    revision_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PlanningInputGaps:
    id: str
    source: str
    confidence: float
    observed_at: str
    created_at: str
    notes: str
    evidence: list[str] = field(default_factory=list)
    status: StatusT = "open"
    gap_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DailyPlanPreview:
    """Read-only compiled day structure — not authoritative until approved flows exist."""

    id: str
    source: str
    confidence: float
    observed_at: str
    created_at: str
    notes: str
    evidence: list[str] = field(default_factory=list)
    status: StatusT = "open"
    today: str = ""
    before_shift: str = ""
    during_shift: str = ""
    after_shift: str = ""
    top_priorities: str = ""
    constraints: str = ""
    risks_to_watch: str = ""
    a_good_day_looks_like: str = ""
    proposed_clickup_actions: list[dict[str, Any]] = field(default_factory=list)
    pending_clarifications: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
