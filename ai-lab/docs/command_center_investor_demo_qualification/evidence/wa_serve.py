def log(msg):
    with open(r"C:\worker\logs\worker_assistant\trace.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")
        f.flush()

log("wa_boot")
from worker_assistant.app import main as wa_main
app = wa_main.app
log("app_loaded " + str(app.title))
import asyncio
import uvicorn
log("imports_ok")

async def main():
    log("main_enter")
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8765,
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
asyncio.run(main())
log("exit")
