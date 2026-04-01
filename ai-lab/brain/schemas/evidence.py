"""
Evidence and fused context schemas (Guru §21).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvidenceItem:
    source_type: str
    title: str | None = None
    path: str | None = None
    content: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    weight: float = 1.0


@dataclass
class LoadedEvidence:
    session_context: dict[str, Any] = field(default_factory=dict)
    local_evidence: list[EvidenceItem] = field(default_factory=list)
    web_evidence: list[EvidenceItem] = field(default_factory=list)
    time_context: dict[str, Any] = field(default_factory=dict)
    sufficient: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass
class FusedContext:
    resolved_question: str
    active_topic: str | None = None
    key_evidence: list[EvidenceItem] = field(default_factory=list)
    secondary_evidence: list[EvidenceItem] = field(default_factory=list)
    time_context: dict[str, Any] = field(default_factory=dict)
    constraints: list[str] = field(default_factory=list)
    recommended_answer_style: str = "direct_status"
    proposal_candidates: list[dict[str, Any]] = field(default_factory=list)
