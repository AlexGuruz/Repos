"""Durable Worker Assistant launcher (Windows-safe asyncio.serve).

Bare ``python -m uvicorn ...`` has been observed to hang before bind on
worker-node when started from detached/SSH sessions. This entrypoint:
- sets no signal handlers (detached-safe)
- uses asyncio.run(server.serve()) which reliably binds
- logs progress to C:\\worker\\logs\\worker_assistant\\trace.txt
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

LOG_DIR = Path(os.environ.get("WORKER_ASSISTANT_LOG_DIR", r"C:\worker\logs\worker_assistant"))
TRACE = LOG_DIR / "trace.txt"
PORT = int(os.environ.get("WORKER_ASSISTANT_PORT", "8765"))
HOST = os.environ.get("WORKER_ASSISTANT_HOST", "0.0.0.0")


def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with TRACE.open("a", encoding="utf-8") as f:
        f.write(msg + "\n")
        f.flush()


def main() -> None:
    if TRACE.exists():
        try:
            TRACE.unlink()
        except OSError:
            pass
    log("wa_boot")
    from worker_assistant.app import main as wa_main

    app = wa_main.app
    log("app_loaded " + str(getattr(app, "title", "?")))
    import uvicorn

    log("imports_ok")

    async def _serve() -> None:
        log("main_enter")
        config = uvicorn.Config(
            app,
            host=HOST,
            port=PORT,
            log_level="info",
            loop="asyncio",
            lifespan="off",
        )
        server = uvicorn.Server(config)
        server.install_signal_handlers = False
        log("serving")
        await server.serve()
        log("serve_done")

    log("asyncio_run")
    asyncio.run(_serve())
    log("exit")


if __name__ == "__main__":
    main()
