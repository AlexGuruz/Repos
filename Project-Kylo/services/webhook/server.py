from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from pydantic import BaseModel, ValidationError
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from services.mover.models import BatchMoveRequest, BatchMoveResponse, CompanyScope
from services.mover.service import MoverService


log = logging.getLogger(__name__)


class WebhookConfig(BaseModel):
    global_dsn: str
    dsn_map_json: str
    signature_secret: Optional[str] = None
    timeout_seconds: int = 15

    @property
    def resolver(self):
        try:
            mapping: Dict[str, str] = json.loads(self.dsn_map_json or "{}")
        except Exception as e:
            raise RuntimeError(f"Invalid KYLO_DB_DSN_MAP JSON: {e}")

        def _resolve(company_id: str) -> str:
            if company_id not in mapping:
                raise KeyError(f"No DSN configured for company_id={company_id}")
            return mapping[company_id]

        return _resolve


def load_config() -> WebhookConfig:
    return WebhookConfig(
        global_dsn=os.environ.get("KYLO_DB_DSN_GLOBAL", "postgresql://postgres:postgres@localhost:5432/kylo_global"),
        dsn_map_json=os.environ.get("KYLO_DB_DSN_MAP", "{}"),
        signature_secret=os.environ.get("KYLO_N8N_SIGNATURE_SECRET"),
        timeout_seconds=int(os.environ.get("KYLO_N8N_TIMEOUT", "15")),
    )


app = FastAPI(title="Kylo Webhook API")


def _verify_signature(header_sig: Optional[str], body: bytes, secret: Optional[str]) -> None:
    if not secret:
        return
    if not header_sig:
        raise HTTPException(status_code=401, detail="Missing signature header")
    # Simple constant-time compare using HMAC-SHA256
    import hmac, hashlib
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(header_sig, digest):
        raise HTTPException(status_code=401, detail="Invalid signature")


@app.post("/webhook/kylo/move-batch")
async def webhook_move_batch(
    request_body: Dict[str, Any],
    x_signature: Optional[str] = Header(default=None, alias="X-Signature"),
):
    raw = json.dumps(request_body).encode("utf-8")
    cfg = load_config()
    _verify_signature(x_signature, raw, cfg.signature_secret)

    try:
        companies = request_body.get("companies") or []
        req = BatchMoveRequest(
            ingest_batch_id=int(request_body["ingest_batch_id"]),
            companies=[CompanyScope(**c) for c in companies] if companies else None,
        )
    except (KeyError, ValueError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")

    svc = MoverService(cfg.global_dsn, cfg.resolver)
    resp: BatchMoveResponse = svc.move_batch(req)
    return JSONResponse(content=json.loads(resp.model_dump_json()))


@app.get("/healthz")
async def healthz():
    return {"ok": True}


