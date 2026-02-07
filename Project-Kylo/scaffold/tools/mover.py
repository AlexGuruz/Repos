from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class CompanyScope:
    company_id: str


@dataclass
class CompanyResult:
    company_id: str
    inserted: int
    updated: int
    enqueued: int
    advanced_to_batch: Optional[int]
    events_emitted: List[str]
    notes: List[str]


@dataclass
class BatchMoveRequest:
    ingest_batch_id: int
    companies: Optional[List[CompanyScope]] = None


@dataclass
class BatchMoveResponse:
    ingest_batch_id: int
    results: List[CompanyResult]
    errors: List[str]


class MoverClient:
    """Skeleton interface for the mover; implementation to be added later.

    Methods operate in batch; no per-row writes.
    """

    def __init__(self, global_dsn: str) -> None:
        self.global_dsn = global_dsn

    def process_batch(self, request: BatchMoveRequest) -> BatchMoveResponse:  # pragma: no cover - skeleton
        raise NotImplementedError


