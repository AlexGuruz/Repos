"""Worker assistant FastAPI app. Run: uvicorn worker_assistant.app.main:app --host 0.0.0.0 --port 8765
Governance: startup runs verify_governance; if fail, app runs read-only (no state-changing endpoints).
"""

import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from worker_assistant.app.routes import (
    health,
    summarize,
    explain_log,
    retrieve,
    index_repo,
    promote_repo_index,
    repo_status,
    ingest_document,
)


def _ensure_governance_on_path() -> None:
    root = os.environ.get("AI_LAB_GOVERNANCE_ROOT", "").strip()
    if not root:
        return
    scripts = Path(root) / "Ai" / "scripts"
    if scripts.is_dir() and str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_governance_on_path()
    try:
        import governance_bridge as gb
        app.state.read_only = not gb.verify_at_startup()
    except Exception:
        app.state.read_only = True
    if getattr(app.state, "read_only", True):
        sys.stderr.write("Worker Assistant: governance verification failed or not set — running read-only (no index_repo).\n")
    yield


app = FastAPI(title="Worker Assistant", version="0.1.0", lifespan=lifespan)

app.include_router(health.router, tags=["health"])
app.include_router(summarize.router, tags=["summarize"])
app.include_router(explain_log.router, tags=["explain"])
app.include_router(retrieve.router, tags=["retrieve"])
app.include_router(index_repo.router, tags=["index"])
app.include_router(promote_repo_index.router, tags=["index"])
app.include_router(repo_status.router, tags=["drift"])
app.include_router(ingest_document.router, tags=["ingest"])


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"ok": False, "error": exc.detail if isinstance(exc.detail, str) else str(exc.detail)},
    )


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": str(exc)},
    )
