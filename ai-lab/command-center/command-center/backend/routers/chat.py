"""
chat.py — routes the command center chat through the real ai-lab
orchestrator rather than the local command-center stub bridge.
"""
import asyncio
import os
import time
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from core.ai_lab import ensure_ai_lab_root_on_path
from core.config import settings
from services.feed_bus import bus
from services.observability import log_api, log_error

ensure_ai_lab_root_on_path()

from brain.orchestrator.main import run as orchestrator_run  # noqa: E402

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    session_id: str = "default"


class ChatResponse(BaseModel):
    role: str = "ai"
    text: str
    act_id: str | None = None
    apr_id: str | None = None
    response_time_ms: int | None = None


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    log_api("chat", "request", message=req.message, history_size=len(req.history))
    await bus.publish("feed", {
        "agent": "user", "op": "sys",
        "detail": req.message[:80],
        "timestamp": datetime.utcnow().isoformat(),
    })
    t0 = time.perf_counter()
    try:
        gov = (settings.ai_lab_governance_root or "").strip()
        if gov:
            os.environ["AI_LAB_GOVERNANCE_ROOT"] = gov
        os.environ["LLM_MAX_OUTPUT_TOKENS"] = str(settings.llm_max_output_tokens)
        result = await asyncio.to_thread(
            orchestrator_run,
            req.message,
            llm_base_url=settings.llm_base_url,
            llm_model=settings.llm_model,
            session_id=req.session_id,
        )
    except Exception as exc:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        log_error("chat", "orchestrator_error", message=req.message, error=str(exc), duration_ms=duration_ms)
        return ChatResponse(text=f"Orchestrator error: {exc}", response_time_ms=duration_ms)

    duration_ms = int((time.perf_counter() - t0) * 1000)
    reply = result.get("reply", "No reply.")
    approval_request = result.get("approval_request") or {}
    apr_id = approval_request.get("id")
    if reply.startswith("[Orchestrator] Intent:"):
        log_api("chat", "llm_fallback", message=req.message, reason="orchestrator_fallback", duration_ms=duration_ms)

    await bus.publish("chat", {
        "role": "ai",
        "text": reply,
        "timestamp": datetime.utcnow().isoformat(),
        "response_time_ms": duration_ms,
    })

    if apr_id:
        pub = {
            "id": apr_id,
            "type": "approval",
            "agent": approval_request.get("agent", "orchestrator"),
            "action": approval_request.get("action_type", "approval"),
            "detail": approval_request.get("reason", ""),
            "status": "pending",
            "timestamp": approval_request.get("created_at", datetime.utcnow().isoformat()),
        }
        cc = approval_request.get("catalog_context")
        if cc:
            pub["catalog_context"] = cc
        await bus.publish("approval", pub)

    log_api(
        "chat",
        "response",
        message=req.message,
        apr_id=apr_id,
        reply_preview=reply[:200],
        duration_ms=duration_ms,
    )
    return ChatResponse(
        text=reply,
        apr_id=apr_id,
        response_time_ms=duration_ms,
    )
