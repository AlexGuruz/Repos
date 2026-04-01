"""Tool usage stats for Tools panel. Placeholder until instrumentation exists."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/tools/stats")
async def tools_stats():
    """Tool calls by agent and data movement. Empty until we add instrumentation."""
    return {
        "toolCalls": [],  # [{ tool, orch, worker, rag, sup }]
        "dataMovement": [],  # [{ op, cls, vol, pct, calls }]
    }
