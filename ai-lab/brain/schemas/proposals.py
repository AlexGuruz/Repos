"""
Proposal record schema (Guru §21, PDR Phase 2.75).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ProposalRecord:
    action: str
    title: str
    description: str
    tool: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    approval_required: bool = True
    expires_after_turns: int = 3
    created_at: str | None = None

    def __post_init__(self) -> None:
        if self.args is None:
            self.args = {}
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "title": self.title,
            "description": self.description,
            "tool": self.tool,
            "args": self.args or {},
            "approval_required": self.approval_required,
            "expires_after_turns": self.expires_after_turns,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ProposalRecord:
        return cls(
            action=d.get("action", ""),
            title=d.get("title", d.get("action", "")),
            description=d.get("description", d.get("title", "")),
            tool=d.get("tool"),
            args=d.get("args") or {},
            approval_required=d.get("approval_required", True),
            expires_after_turns=d.get("expires_after_turns", 3),
            created_at=d.get("created_at"),
        )
