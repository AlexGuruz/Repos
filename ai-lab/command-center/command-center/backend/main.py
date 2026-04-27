"""
main.py — AI Lab Command Center backend
Runs on main rig only. Fails closed if governance env is wrong.
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import settings, verify_governance
from core.ai_lab import AI_LAB_ROOT
from routers import chat, events, guru, hardware, prepared_context, repo, repo_index, tools, workers
from services.nvidia_poller import nvidia_poll_loop
from services.prepared_context_refresher import run_prepared_context_refresher
from services.repo_watcher import start_watcher, stop_watcher, WATCH_PATHS
from services.repo_index_coordinator import get_coordinator


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Governance gate — fails closed
    verify_governance()

    # Seed watch paths from governance root and env
    if settings.ai_lab_governance_root:
        WATCH_PATHS.append(settings.ai_lab_governance_root)
    WATCH_PATHS.extend(settings.watch_paths_list)
    # Fallback: watch ai-lab repo so Repo Tracker gets events when no root configured
    if not WATCH_PATHS and AI_LAB_ROOT.exists():
        WATCH_PATHS.append(str(AI_LAB_ROOT))

    # Start background tasks
    loop = asyncio.get_running_loop()
    start_watcher(loop)
    poller_task = asyncio.create_task(nvidia_poll_loop())
    prepared_context_task = asyncio.create_task(run_prepared_context_refresher())
    coordinator = get_coordinator()
    coordinator_task = asyncio.create_task(coordinator.run_forever())

    yield

    # Shutdown
    poller_task.cancel()
    prepared_context_task.cancel()
    coordinator_task.cancel()
    try:
        await coordinator.stop()
    except Exception:
        pass
    stop_watcher()


app = FastAPI(
    title="AI Lab Command Center",
    version="0.1.0",
    lifespan=lifespan,
)

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
app.include_router(workers.router)
app.include_router(prepared_context.router)


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
        async with httpx.AsyncClient(timeout=30.0) as client:
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


@app.get("/api/health")
async def health(llm: str | None = None):
    """Basic health plus LLM. Add ?llm=1 to run LM Studio native /api/v1/chat test and see raw response/error."""
    import httpx
    from urllib.parse import urlparse
    llm_base_url = (settings.llm_base_url or "").strip()
    llm_model = (settings.llm_model or "").strip()
    llm_reachable = False
    if llm_base_url:
        try:
            url = llm_base_url.rstrip("/") + "/models"
            async with httpx.AsyncClient(timeout=2.0) as client:
                r = await client.get(url)
                llm_reachable = r.status_code == 200
        except Exception:
            pass
    out = {
        "ok": True,
        "machine": settings.ai_lab_machine,
        "enforcement": settings.ai_lab_enforcement,
        "worker_url": settings.worker_tunnel_url,
        "llm_base_url": llm_base_url or None,
        "llm_model": llm_model or None,
        "llm_reachable": llm_reachable,
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
