"""
chat.py — routes the command center chat through the real ai-lab
orchestrator rather than the local command-center stub bridge.
"""
import asyncio
import json
import os
import queue as sync_queue
import threading
import time
import uuid
from datetime import datetime

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.ai_lab import ensure_ai_lab_root_on_path
from core.config import settings
from services.channels import channels
from services.executors import CHAT_EXECUTOR, run_in
from services.observability import log_api, log_error

ensure_ai_lab_root_on_path()

from brain.orchestrator.main import run as orchestrator_run  # noqa: E402

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    session_id: str = "default"
    request_id: str | None = None
    client_submit_epoch_ms: float | None = None


class ChatResponse(BaseModel):
    role: str = "ai"
    text: str
    act_id: str | None = None
    apr_id: str | None = None
    response_time_ms: int | None = None


def _apply_chat_env():
    gov = (settings.ai_lab_governance_root or "").strip()
    if gov:
        os.environ["AI_LAB_GOVERNANCE_ROOT"] = gov
    os.environ["LLM_MAX_OUTPUT_TOKENS"] = str(settings.llm_max_output_tokens)


async def _publish_chat_side_effects(
    reply: str,
    approval_request: dict,
    duration_ms: int,
    *,
    publish_ws_chat: bool = True,
):
    apr_id = approval_request.get("id")
    if publish_ws_chat:
        await channels.chat.publish(
            "chat",
            {
                "role": "ai",
                "text": reply,
                "timestamp": datetime.utcnow().isoformat(),
                "response_time_ms": duration_ms,
            },
        )
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
        fp = approval_request.get("file_path")
        if fp:
            pub["file_path"] = fp
        pl = approval_request.get("payload")
        if isinstance(pl, dict) and pl:
            pub["payload"] = pl
        await channels.control.publish("approval", pub)


@router.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    log_api("chat", "request", message=req.message, history_size=len(req.history))
    await channels.ops.publish(
        "feed",
        {
            "agent": "user",
            "op": "sys",
            "detail": req.message[:80],
            "timestamp": datetime.utcnow().isoformat(),
        },
    )
    t0 = time.perf_counter()
    recv_wall = time.time() * 1000.0
    rid = (req.request_id or "").strip() or str(uuid.uuid4())
    try:
        _apply_chat_env()
        result = None
        try:
            from operator_desk.fast_path import try_fast_reply

            fast = try_fast_reply(req.message)
            if isinstance(fast, dict) and fast.get("reply"):
                result = fast
        except Exception:
            result = None
        if result is None:
            result = await run_in(
                CHAT_EXECUTOR,
                lambda: orchestrator_run(
                    req.message,
                    llm_base_url=settings.llm_base_url,
                    llm_model=settings.llm_model,
                    session_id=req.session_id,
                    request_id=rid,
                    client_submit_epoch_ms=req.client_submit_epoch_ms,
                    receive_wall_ms=recv_wall,
                ),
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

    await _publish_chat_side_effects(reply, approval_request, duration_ms, publish_ws_chat=True)

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


@router.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """SSE stream of LLM token deltas + final JSON (avoids duplicate WS chat when UI reads stream)."""
    log_api("chat", "stream_request", message=req.message, history_size=len(req.history))
    await channels.ops.publish(
        "feed",
        {
            "agent": "user",
            "op": "sys",
            "detail": req.message[:80],
            "timestamp": datetime.utcnow().isoformat(),
        },
    )

    async def event_gen():
        sq: sync_queue.Queue = sync_queue.Queue()
        result_h: dict = {}
        err_h: dict = {}
        recv_wall = time.time() * 1000.0
        rid = (req.request_id or "").strip() or str(uuid.uuid4())

        def push_delta(t: str) -> None:
            if t:
                sq.put(("d", t))

        def worker() -> None:
            try:
                _apply_chat_env()
                fast = None
                try:
                    from operator_desk.fast_path import try_fast_reply

                    fast = try_fast_reply(req.message)
                except Exception:
                    fast = None
                if isinstance(fast, dict) and fast.get("reply"):
                    result_h["r"] = fast
                    push_delta(str(fast.get("reply") or ""))
                else:
                    result_h["r"] = orchestrator_run(
                        req.message,
                        llm_base_url=settings.llm_base_url,
                        llm_model=settings.llm_model,
                        session_id=req.session_id,
                        stream_delta=push_delta,
                        request_id=rid,
                        client_submit_epoch_ms=req.client_submit_epoch_ms,
                        receive_wall_ms=recv_wall,
                    )
            except Exception as e:
                err_h["e"] = str(e)
            finally:
                sq.put(("x", None))

        t0 = time.perf_counter()
        th = threading.Thread(target=worker, daemon=True)
        th.start()

        def _pull():
            try:
                return sq.get(timeout=0.35)
            except sync_queue.Empty:
                return None

        # Keep the connection warm during long LLM/tool work (proxies idle-timeout, UI liveness).
        last_hb = time.monotonic()
        hb_interval_sec = 12.0

        try:
            while th.is_alive() or not sq.empty():
                item = await run_in(CHAT_EXECUTOR, _pull)
                if item is None:
                    if th.is_alive() and (time.monotonic() - last_hb) >= hb_interval_sec:
                        last_hb = time.monotonic()
                        yield f"data: {json.dumps({'hb': True})}\n\n"
                    continue
                kind, payload = item
                if kind == "d":
                    yield f"data: {json.dumps({'delta': payload})}\n\n"
                elif kind == "x":
                    break
        finally:
            th.join(timeout=300)

        duration_ms = int((time.perf_counter() - t0) * 1000)

        if err_h.get("e"):
            log_error("chat", "stream_orchestrator_error", message=req.message, error=err_h["e"], duration_ms=duration_ms)
            yield f"data: {json.dumps({'error': err_h['e'], 'done': True, 'response_time_ms': duration_ms})}\n\n"
            return

        result = result_h.get("r") or {}
        reply = result.get("reply", "No reply.")
        approval_request = result.get("approval_request") or {}
        apr_id = approval_request.get("id")

        await _publish_chat_side_effects(reply, approval_request, duration_ms, publish_ws_chat=False)

        log_api(
            "chat",
            "stream_response",
            message=req.message,
            apr_id=apr_id,
            reply_preview=reply[:200],
            duration_ms=duration_ms,
        )
        yield f"data: {json.dumps({'done': True, 'text': reply, 'apr_id': apr_id, 'response_time_ms': duration_ms})}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
