from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


class CompanyScope(BaseModel):
    company_id: str


class CompanyResult(BaseModel):
    company_id: str
    inserted: int
    updated: int
    enqueued: int
    advanced_to_batch: Optional[int]
    events_emitted: List[str]
    notes: List[str] = []


class BatchMoveRequest(BaseModel):
    ingest_batch_id: int
    companies: Optional[List[CompanyScope]] = None


class BatchMoveResponse(BaseModel):
    ingest_batch_id: int
    results: List[CompanyResult]
    errors: List[str] = []


