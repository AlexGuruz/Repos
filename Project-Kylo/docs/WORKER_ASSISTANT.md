# Worker Assistant (AI Lab)

FastAPI service on the worker rig that serves Ollama-backed retrieval and repo indexing. It listens on port **8765** and is intended to be reached from the main rig (ACHERON) via an SSH tunnel.

## Rig names and tunnel

- **Main rig:** ACHERON — start the tunnel here and run drift scan.
- **Worker rig:** worker-node — runs worker_assistant; no tunnel command on this machine.

See **[WORKER_AI_STATUS.md](WORKER_AI_STATUS.md)** for the full checklist, plan status (M1–M6A), and rig definitions.

## One script (run on ACHERON)

From the main rig, run this. It starts the tunnel if needed (SSH window for password if required), then runs the drift scan:

```powershell
& "E:\Repos\Project-Kylo\scripts\worker_ai\run_drift_scan.ps1"
```

Manual tunnel (use `127.0.0.1` on remote for IPv4):

```powershell
ssh -L 8765:127.0.0.1:8765 worker@192.168.40.25 -N
```

Then in another window: `& "E:\Repos\Project-Kylo\scripts\worker_ai\drift_scan.ps1" -BaseUrl "http://127.0.0.1:8765"`

## Endpoints

- `GET /health` — health check
- `GET /repo_status` — repo indexing status (ensure worker runs code that has this route)
- `POST /retrieve` — retrieval (e.g. for drift scan)
- `POST /index_repo` (or equivalent) — trigger indexing

If you get 404 for `/repo_status`, restart worker_assistant on the worker from the repo that implements that route.
