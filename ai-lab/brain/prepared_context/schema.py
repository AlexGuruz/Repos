"""
Prepared context snapshot schema and validation helpers.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class PreparedSnapshot:
    snapshot_type: str
    generated_at: str
    freshness_seconds: int
    source_files_or_tools: list[str]
    confidence: float
    stale: bool
    errors: list[str]
    data: dict[str, Any]
    summary_short: str
    summary_detailed: str
    suggested_questions: list[str]
    evidence_items: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def validate_snapshot_dict(payload: dict[str, Any]) -> tuple[bool, list[str]]:
    required = [
        "snapshot_type",
        "generated_at",
        "freshness_seconds",
        "source_files_or_tools",
        "confidence",
        "stale",
        "errors",
        "data",
        "summary_short",
        "summary_detailed",
        "suggested_questions",
        "evidence_items",
    ]
    errs: list[str] = []
    if not isinstance(payload, dict):
        return False, ["payload must be an object"]
    for k in required:
        if k not in payload:
            errs.append(f"missing field: {k}")
    if errs:
        return False, errs
    if not isinstance(payload.get("snapshot_type"), str) or not payload["snapshot_type"].strip():
        errs.append("snapshot_type must be non-empty string")
    if not isinstance(payload.get("freshness_seconds"), int) or payload["freshness_seconds"] <= 0:
        errs.append("freshness_seconds must be positive int")
    if not isinstance(payload.get("source_files_or_tools"), list):
        errs.append("source_files_or_tools must be list")
    if not isinstance(payload.get("confidence"), (float, int)):
        errs.append("confidence must be number")
    if not isinstance(payload.get("stale"), bool):
        errs.append("stale must be bool")
    if not isinstance(payload.get("errors"), list):
        errs.append("errors must be list")
    if not isinstance(payload.get("data"), dict):
        errs.append("data must be object")
    if not isinstance(payload.get("summary_short"), str):
        errs.append("summary_short must be string")
    if not isinstance(payload.get("summary_detailed"), str):
        errs.append("summary_detailed must be string")
    if not isinstance(payload.get("suggested_questions"), list):
        errs.append("suggested_questions must be list")
    if not isinstance(payload.get("evidence_items"), list):
        errs.append("evidence_items must be list")
    return len(errs) == 0, errs

