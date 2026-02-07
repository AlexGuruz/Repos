from pydantic import BaseModel, Field
from typing import Optional, Dict, List, Literal

class Routing(BaseModel):
    db_dsn_rw: str
    db_schema: str
    spreadsheet_id: str
    tab_pending: str
    tab_active: str

class TxnsBatchMessage(BaseModel):
    event_type: Literal["TXNS_BATCH"] = "TXNS_BATCH"
    version: int = 1
    batch_id: str              # ULID/UUID for this publish
    company_id: str
    ingest_batch_id: int
    routing: Routing
    slice_signature: str       # deterministic hash for dedupe/sanity
    created_at: str            # ISO8601
    meta: Optional[Dict] = None

class PromoteRequestMessage(BaseModel):
    event_type: Literal["PROMOTE_RULES"] = "PROMOTE_RULES"
    version: int = 1
    company_id: str
    routing: Routing
    created_at: str
    meta: Optional[Dict] = None
