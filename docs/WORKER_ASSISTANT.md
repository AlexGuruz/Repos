# Worker Assistant (worker_assistant)

FastAPI service on the worker rig that serves Ollama-backed retrieval and repo indexing. It listens on port **8765** (LAN bind on the worker).

## Endpoints

- **GET /health** – liveness
- **GET /repo_status** – repo indexing status (used by drift scan)
- **POST /retrieve** – semantic retrieval (query + top_k)
- **POST /index_repo** – trigger indexing (or use scheduled job on worker)

## Reaching it from the main rig (ACHERON)

The tunnel runs **from the main rig to the worker**. On ACHERON:

```powershell
ssh -L 8765:localhost:8765 worker@192.168.40.25 -N
```

Then use `http://127.0.0.1:8765` as the base URL (e.g. for drift scan or scripts).

For rig names, full checklist, and script paths see **[WORKER_AI_STATUS.md](WORKER_AI_STATUS.md)**.
