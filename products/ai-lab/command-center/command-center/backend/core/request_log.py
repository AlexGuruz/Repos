"""Structured request logging with X-Request-ID."""
from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = (request.headers.get("x-request-id") or "").strip() or uuid.uuid4().hex[:12]
        request.state.request_id = rid
        started = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        except Exception as exc:
            try:
                from services.observability import log_error

                log_error(
                    "http",
                    str(exc)[:400],
                    request_id=rid,
                    method=request.method,
                    path=request.url.path,
                )
            except Exception:
                pass
            raise
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            try:
                from services.observability import log_api

                log_api(
                    "http",
                    "request",
                    request_id=rid,
                    method=request.method,
                    path=request.url.path,
                    status=status,
                    duration_ms=duration_ms,
                )
            except Exception:
                pass
