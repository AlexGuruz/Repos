from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, TypeVar

from services.common.config_loader import load_config

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 5
    base_delay_secs: float = 1.5
    max_delay_secs: float = 60.0
    jitter_ratio: float = 0.5  # +-50% jitter


def _default_policy() -> RetryPolicy:
    # Prefer YAML google.retry.*, fall back to environment defaults.
    try:
        cfg = load_config()
        max_attempts = int(cfg.get("google.retry.max_attempts", 5) or 5)
        base_delay = float(cfg.get("google.retry.base_delay_secs", 1.5) or 1.5)
        max_delay = float(cfg.get("google.retry.max_delay_secs", 60.0) or 60.0)
        return RetryPolicy(max_attempts=max_attempts, base_delay_secs=base_delay, max_delay_secs=max_delay)
    except Exception:
        return RetryPolicy()


def _extract_http_status(exc: Exception) -> Optional[int]:
    # googleapiclient.errors.HttpError has .resp.status
    try:
        resp = getattr(exc, "resp", None)
        status = getattr(resp, "status", None)
        if status is None:
            status = getattr(resp, "status_code", None)
        return int(status) if status is not None else None
    except Exception:
        return None


def _is_retryable(exc: Exception) -> bool:
    status = _extract_http_status(exc)
    if status in (429, 500, 502, 503, 504):
        return True
    if status == 403:
        # Google APIs frequently use 403 for quota/rate limiting (but also for permission denied).
        # Only retry when we can detect a rate/quota subtype in the error text.
        msg = str(exc).lower()
        if any(
            token in msg
            for token in (
                "ratelimitexceeded",
                "userratelimitexceeded",
                "quotaexceeded",
                "rate limit exceeded",
                "user rate limit exceeded",
                "quota exceeded",
            )
        ):
            return True
    # Common transient network/timeouts from requests/httplib2
    name = exc.__class__.__name__.lower()
    msg = str(exc).lower()
    if "timeout" in name or "timedout" in name:
        return True
    if "timeout" in msg or "timed out" in msg:
        return True
    if "connection reset" in msg or "connection aborted" in msg or "temporarily unavailable" in msg:
        return True
    return False


def _sleep_for_attempt(policy: RetryPolicy, attempt_idx: int) -> float:
    # attempt_idx: 0 for first retry delay
    delay = policy.base_delay_secs * (2 ** max(0, attempt_idx))
    delay = min(policy.max_delay_secs, delay)
    jitter = delay * policy.jitter_ratio
    return max(0.0, delay + random.uniform(-jitter, jitter))


def retry_call(fn: Callable[[], T], *, policy: RetryPolicy | None = None, label: str = "") -> T:
    pol = policy or _default_policy()
    last_exc: Exception | None = None
    for attempt in range(1, pol.max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if attempt >= pol.max_attempts or not _is_retryable(e):
                raise
            sleep_s = _sleep_for_attempt(pol, attempt_idx=attempt - 1)
            time.sleep(sleep_s)
    # unreachable
    assert last_exc is not None
    raise last_exc


def google_api_execute(req: Any, *, policy: RetryPolicy | None = None, label: str = "") -> Any:
    """Execute a googleapiclient request with retry/backoff."""

    def _do():
        return req.execute()

    return retry_call(_do, policy=policy, label=label)

