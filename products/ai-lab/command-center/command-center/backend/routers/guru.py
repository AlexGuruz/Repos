from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.channels import channels
from services.guru_service import confirm_mode, get_mode, revert_last, snapshot, submit_mode_message
from services.observability import log_api, log_error


router = APIRouter()


class GuruMessageRequest(BaseModel):
    message: str


@router.get("/api/guru")
async def guru_snapshot():
    log_api("guru", "snapshot")
    return snapshot()


@router.get("/api/guru/{mode}")
async def guru_mode(mode: str):
    try:
        log_api("guru", "get_mode", mode=mode.upper())
        return get_mode(mode)
    except KeyError as exc:
        log_error("guru", "unknown_mode", mode=mode)
        raise HTTPException(status_code=404, detail=f"Unknown Guru mode '{mode}'.") from exc


@router.post("/api/guru/{mode}/message")
async def guru_mode_message(mode: str, body: GuruMessageRequest):
    try:
        log_api("guru", "message", mode=mode.upper(), text=body.message)
        result = submit_mode_message(mode, body.message)
    except KeyError as exc:
        log_error("guru", "unknown_mode", mode=mode, action="message")
        raise HTTPException(status_code=404, detail=f"Unknown Guru mode '{mode}'.") from exc
    except ValueError as exc:
        log_error("guru", "invalid_message", mode=mode, error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await channels.ops.publish(
        "feed",
        {
            "agent": "guru",
            "op": "write" if result.get("saved") else "sys",
            "detail": result.get("summary", f"{mode.upper()} updated"),
            "timestamp": result.get("last_updated_at"),
        },
    )
    log_api("guru", "message_result", mode=mode.upper(), saved=result.get("saved"), summary=result.get("summary"))
    return result


@router.post("/api/guru/{mode}/confirm")
async def guru_mode_confirm(mode: str):
    try:
        log_api("guru", "confirm", mode=mode.upper())
        result = confirm_mode(mode)
    except KeyError as exc:
        log_error("guru", "unknown_mode", mode=mode, action="confirm")
        raise HTTPException(status_code=404, detail=f"Unknown Guru mode '{mode}'.") from exc
    except ValueError as exc:
        log_error("guru", "confirm_error", mode=mode, error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await channels.ops.publish(
        "feed",
        {
            "agent": "guru",
            "op": "write",
            "detail": result.get("summary", f"{mode.upper()} confirmed"),
            "timestamp": result.get("last_updated_at"),
        },
    )
    log_api("guru", "confirm_result", mode=mode.upper(), summary=result.get("summary"))
    return result


@router.post("/api/guru/{mode}/revert")
async def guru_mode_revert(mode: str):
    try:
        log_api("guru", "revert", mode=mode.upper())
        result = revert_last(mode)
    except KeyError as exc:
        log_error("guru", "unknown_mode", mode=mode, action="revert")
        raise HTTPException(status_code=404, detail=f"Unknown Guru mode '{mode}'.") from exc
    except ValueError as exc:
        log_error("guru", "revert_error", mode=mode, error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await channels.ops.publish(
        "feed",
        {
            "agent": "guru",
            "op": "write",
            "detail": result.get("summary", f"{mode.upper()} reverted"),
            "timestamp": result.get("last_updated_at"),
        },
    )
    log_api("guru", "revert_result", mode=mode.upper(), summary=result.get("summary"))
    return result
