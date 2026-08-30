"""
main.py — AI Lab Command Center backend
Runs on main rig only. Fails closed if governance env is wrong.
"""
import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env into os.environ so Operator Desk and other libs see flags.
# Do not clobber Compose/systemd env with a Windows .env copied onto Linux.
load_dotenv(Path(__file__).resolve().parent / ".env", override=False)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings, verify_governance
from core.request_log import RequestIdMiddleware
from core.ai_lab import AI_LAB_ROOT
from routers import chat, events, guru, hardware, live_work, prepared_context, repo, repo_docs, repo_index, retail, tools, tunnel, workers
from services.nvidia_poller import nvidia_poll_loop
from services.prepared_context_refresher import run_prepared_context_refresher
from services.repo_watcher import start_watcher, stop_watcher, WATCH_PATHS
from services.repo_index_coordinator import get_coordinator
from services.channels import channels
from services.tunnel_scheduler import tunnel_scheduler
from services.observability import ensure_legacy_event_stream_not_appended


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Governance gate — fails closed
    import logging
    log = logging.getLogger("uvicorn.error")
    log.info("lifespan: verify_governance")
    verify_governance()

    # Never append to oversized legacy event_stream.jsonl
    log.info("lifespan: legacy stream guard")
    ensure_legacy_event_stream_not_appended()

    # Seed watch paths from governance root and env
    gov = settings.ai_lab_governance_root
    if gov and not (os.name != "nt" and len(gov) >= 2 and gov[1] == ":"):
        WATCH_PATHS.append(gov)
    WATCH_PATHS.extend(settings.watch_paths_list)
    # Fallback: watch ai-lab repo so Repo Tracker gets events when no root configured
    if not WATCH_PATHS and AI_LAB_ROOT.exists():
        WATCH_PATHS.append(str(AI_LAB_ROOT))

    log.info("lifespan: channels")
    await channels.start()
    log.info("lifespan: tunnel_scheduler")
    await tunnel_scheduler.start()

    # Start background tasks
    loop = asyncio.get_running_loop()
    # Recursive watchdog on /ai-lab can take minutes; do not block :8000 bind.
    loop.run_in_executor(None, start_watcher, loop)
    log.info("lifespan: watcher scheduled")
    light = str(os.environ.get("CC_LIGHT_MODE", "")).strip().lower() in {"1", "true", "yes"}
    poller_task = prepared_context_task = coordinator_task = None
    log.info("lifespan: coordinator")
    coordinator = get_coordinator()
    if not light:
        poller_task = asyncio.create_task(nvidia_poll_loop())
        prepared_context_task = asyncio.create_task(run_prepared_context_refresher())
        coordinator_task = asyncio.create_task(coordinator.run_forever())
    log.info("lifespan: ready light=%s", light)

    yield

    # Shutdown
    for task in (poller_task, prepared_context_task, coordinator_task):
        if task is not None:
            task.cancel()
    try:
        await coordinator.stop()
    except Exception:
        pass
    stop_watcher()
    try:
        await tunnel_scheduler.stop()
    except Exception:
        pass
    try:
        await channels.stop()
    except Exception:
        pass
    try:
        from routers.retail import close_client as _close_retail_client
        await _close_retail_client()
    except Exception:
        pass


app = FastAPI(
    title="AI Lab Command Center",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(events.router)
app.include_router(guru.router)
app.include_router(hardware.router)
app.include_router(repo.router)
app.include_router(repo_index.router)
app.include_router(tools.router)
app.include_router(tunnel.router)
app.include_router(workers.router)
app.include_router(prepared_context.router)
app.include_router(repo_docs.router)
app.include_router(live_work.router)
app.include_router(retail.router)

# Operator Desk — optional; disabled by default (OPERATOR_DESK_ENABLED=1 to activate routes)
try:
    from operator_desk.api.router import is_router_enabled, router as operator_router

    if is_router_enabled():
        app.include_router(operator_router)
except Exception:
    pass


@app.get("/api/llm-status")
async def llm_status():
    """
    Verify command-center chat will use LM Studio: compares LLM_MODEL to GET /v1/models ids.
    Open in browser while LM Studio server is running.
    """
    from brain.llm_client import get_llm_connection_status

    return get_llm_connection_status(settings.llm_base_url, settings.llm_model)


@app.get("/api/llm-test")
async def llm_test():
    """Call LM Studio native /api/v1/chat and return raw response/error for debugging."""
    import httpx
    from urllib.parse import urlparse
    base = (settings.llm_base_url or "").strip().rstrip("/")
    model = (settings.llm_model or "").strip()
    if not base:
        return {"error": "llm_base_url not set", "url": None, "response": None}
    u = urlparse(base)
    server = f"{u.scheme}://{u.netloc}"
    url = server + "/api/v1/chat"
    body = {
        "model": model or "qwen2.5-coder-14b-instruct",
        "input": "Say hello in one word.",
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(url, json=body)
            try:
                resp_json = r.json()
            except Exception:
                resp_json = r.text
            return {
                "url": url,
                "model": body["model"],
                "status_code": r.status_code,
                "response": resp_json,
                "error": None if r.is_success else r.text[:500],
            }
    except Exception as e:
        return {
            "url": url,
            "model": body["model"],
            "status_code": None,
            "response": None,
            "error": str(e),
        }


@app.get("/api/channels/metrics")
async def channel_metrics():
    """Per-channel publish/delivery/drop metrics for isolation health."""
    return {"ok": True, "channels": channels.metrics(), "tunnel": tunnel_scheduler.snapshot()}


@app.get("/api/operator/status")
async def operator_status():
    """
    One-shot operator digest: channels + tunnel + pending + WA critical.
    Daily SoT companion to docs/command_center_production/OPERATOR_STATUS.md
    """
    try:
        from core.ai_lab import ensure_ai_lab_root_on_path

        ensure_ai_lab_root_on_path()
        from brain.approval_queue.queue import list_pending
        from services.worker_fleet import health_for

        # Never block the asyncio loop on pending disk IO or WA HTTP probes.
        pending_n = await asyncio.to_thread(lambda: len(list_pending()))
        snap = await asyncio.to_thread(health_for, "power-1")
        wa = {
            "critical_ok": bool(snap.get("critical_ok")),
            "worker_assistant_ok": bool(snap.get("worker_assistant_ok")),
            "all_ok": bool(snap.get("all_ok")),
            "worker_status": snap.get("worker_status"),
            "worker_name": snap.get("worker_name"),
        }
    except Exception as exc:
        pending_n = None
        wa = {"error": str(exc)[:200]}

    light = str(os.environ.get("CC_LIGHT_MODE", "")).strip().lower() in {"1", "true", "yes"}
    return {
        "ok": True,
        "full_mode": not light,
        "cc_light_mode": light,
        "pending_count": pending_n,
        "workers": wa,
        "channels": channels.metrics(),
        "tunnel": tunnel_scheduler.snapshot(),
        "daily_tools": {
            "smoke_only": ["cc_investor_demo_ping"],
            "product_default": (
                "Operator Desk allowlisted tools "
                "(growflow_*, operator_*, machine propose)"
            ),
            "docs": "docs/command_center_production/OPERATOR_STATUS.md",
        },
        "ws": {
            "preferred": ["/ws/control", "/ws/ops", "/ws/chat", "/ws/telemetry"],
            "deprecated": "/ws/events",
        },
    }


_LLM_PROBE_CACHE: dict[str, float | bool] = {"at": 0.0, "reachable": False}
_LLM_PROBE_TTL_S = 10.0
_health_httpx: "httpx.AsyncClient | None" = None


def _get_health_client():
    """Reuse one httpx client; building one per request blocks the event loop."""
    global _health_httpx
    import httpx
    if _health_httpx is None or _health_httpx.is_closed:
        _health_httpx = httpx.AsyncClient(timeout=2.0)
    return _health_httpx


@app.get("/api/health")
async def health(llm: str | None = None):
    """Basic health plus LLM. Add ?llm=1 to run LM Studio native /api/v1/chat test and see raw response/error."""
    import time as _time
    import httpx
    from urllib.parse import urlparse
    llm_base_url = (settings.llm_base_url or "").strip()
    llm_model = (settings.llm_model or "").strip()
    # Cache reachability so frequent health polls don't each pay the probe cost
    # (and never block the event loop for 2s on every request when LLM is down).
    now = _time.monotonic()
    if llm_base_url and (now - float(_LLM_PROBE_CACHE["at"])) > _LLM_PROBE_TTL_S:
        _LLM_PROBE_CACHE["at"] = now
        try:
            url = llm_base_url.rstrip("/") + "/models"
            r = await _get_health_client().get(url)
            _LLM_PROBE_CACHE["reachable"] = r.status_code == 200
        except Exception:
            _LLM_PROBE_CACHE["reachable"] = False
    llm_reachable = bool(_LLM_PROBE_CACHE["reachable"]) if llm_base_url else False
    out = {
        "ok": True,
        "machine": settings.ai_lab_machine,
        "enforcement": settings.ai_lab_enforcement,
        "worker_url": settings.worker_tunnel_url,
        "llm_base_url": llm_base_url or None,
        "llm_model": llm_model or None,
        "llm_reachable": llm_reachable,
        "channels": channels.metrics(),
    }
    if llm and llm_base_url:
        u = urlparse(llm_base_url.rstrip("/"))
        server = f"{u.scheme}://{u.netloc}"
        url = server + "/api/v1/chat"
        body = {"model": (llm_model or "qwen2.5-coder-14b-instruct").strip().lower(), "input": "Say hello.", "stream": False}
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                r = await client.post(url, json=body)
                try:
                    resp_json = r.json()
                except Exception:
                    resp_json = r.text
                out["llm_test"] = {"url": url, "status_code": r.status_code, "response": resp_json, "error": None if r.is_success else (r.text[:500] if r.text else str(r.status_code))}
        except Exception as e:
            err_msg = str(e) or f"{type(e).__name__}"
            out["llm_test"] = {"url": url, "status_code": None, "response": None, "error": err_msg}
    return out
