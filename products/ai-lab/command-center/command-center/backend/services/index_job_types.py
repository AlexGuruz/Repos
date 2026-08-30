from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal


class JobType(str, Enum):
    incremental_staging = "incremental_staging"
    repo_refresh_staging = "repo_refresh_staging"
    full_rebuild_staging_gate_a = "full_rebuild_staging_gate_a"
    full_rebuild_staging_gate_c = "full_rebuild_staging_gate_c"
    blocked_pending_approval = "blocked_pending_approval"


class ApprovalGate(str, Enum):
    A = "A"
    C = "C"


@dataclass(frozen=True)
class JobPlan:
    job_type: JobType
    worker_target: Literal["staging"]
    worker_mode: Literal["incremental", "repo_refresh", "full_rebuild"]
    force_full: bool
    requires_approval: bool
    approval_gate: ApprovalGate | None


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    severity: Literal["ok", "retryable", "gate_a", "gate_c", "escalate"]
    reasons: list[str]


@dataclass(frozen=True)
class BuildMetadata:
    """
    Worker-reported identity + counters for strict validation before promote.
    Stored as a flat bag so coordinator can compare fields reliably.
    """

    repo_id: str
    target: str
    build_id: str
    staging_version: str | None
    active_version_seen: str | None

    embedding_model_id_used: str | None
    embedding_model_revision_used: str | None
    policy_hash_used: str | None
    index_schema_version_used: int | None
    collection_layout_version_used: int | None
    metadata_readable: bool | None
    corruption_detected: bool | None

    files_considered: int | None
    files_indexed: int | None
    chunks_indexed: int | None

    started_at: str | None
    finished_at: str | None

    warnings: list[str]
    errors: list[str]
    raw: dict[str, Any]

