"""Named bounded thread pools for Command Center isolation."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable

APPROVAL_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cc-approvals")
TELEMETRY_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cc-telemetry")
CHAT_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cc-chat")
CONTEXT_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cc-context")
EXEC_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="cc-exec")


async def run_in(executor: ThreadPoolExecutor, fn: Callable[..., Any], /, *args: Any) -> Any:
    import asyncio

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, fn, *args)
