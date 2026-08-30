# ai-lab · command center

Command center app at `ai-lab/command-center/command-center/`.
This is the operator UI/API layer that fronts `brain/` orchestration and governance data.

Canonical cross-references:

- `../../README.md`
- `../../docs_source/DOCUMENTATION_STANDARD.md`
- `../../docs_source/WORKER_CURRENT.md`
- `../../docs_source/contracts/worker.md`

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 18 + Vite + Tailwind |
| Backend | FastAPI + Uvicorn |
| Real-time | WebSocket (event bus) |
| Hardware | `nvidia-smi` poller (5 s interval) |
| State | Zustand (frontend) |

## Layout

```
command-center/
├── frontend/          # Vite + React UI
│   └── src/
│       ├── components/    # Sidebar, Chat, Compute, Feed, Repo, Tools
│       ├── hooks/         # useWebSocket, useNvidiaSmi
│       ├── lib/           # api.js, ws.js
│       └── store/         # Zustand stores
├── backend/           # FastAPI
│   ├── main.py
│   ├── routers/       # chat, events, hardware, repo
│   ├── services/      # supervisor_bridge, nvidia_poller, feed_bus
│   └── core/          # config, governance, models
├── scripts/           # start.sh, start.ps1, bootstrap/deps helpers
└── docker-compose.yml
```

## Quick start

### Linux (Acheron / daily path)
```bash
cd /mnt/workshop/Repos/products/ai-lab/command-center/command-center
./scripts/start.sh          # docker compose up (default)
./scripts/harness.sh        # health + pytest + vitest
```
`start.sh` sets `AI_LAB_ROOT` and prefers Compose (`network_mode: host` so the API sees tunnels on `127.0.0.1:8765`). To run uvicorn+vite on the host instead: `CC_USE_COMPOSE=0 ./scripts/start.sh`.

UI → http://127.0.0.1:5173 · API → http://127.0.0.1:8000 · Health → http://127.0.0.1:8000/api/health

### Windows (PowerShell) — legacy
```powershell
cd ai-lab\command-center\command-center
.\scripts\start.ps1 -FullMode
```
`-FullMode` → `CC_LIGHT_MODE=0`. Plain `.\scripts\start.ps1` is light-mode and is **not** the daily path. See **BOOT.md**.

**Pending backlog hygiene (before sessions):** from ai-lab root, dry-run then apply:  
`python scripts/archive_stale_pending_approvals.py` → `python scripts/archive_stale_pending_approvals.py --apply`  
UI: Sidebar → Dismiss APR stubs (APR-* only; does not touch brain `approval-N`).

### Manual
```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

UI → http://localhost:5173  
API → http://localhost:8000  
WS  → ws://localhost:8000/ws/events  

**Tabs:** Chat, Compute, Guru, etc. stay **mounted** when you switch (only hidden). In-flight chat, WebSocket updates, and Compute polling keep running in the background.

## Environment

Copy `.env.example` → `.env` and fill in:

```
AI_LAB_ROOT=/mnt/workshop/Repos/products/ai-lab
AI_LAB_GOVERNANCE_ROOT=/mnt/workshop/Repos/products/ai-lab-governance
AI_LAB_MACHINE=main
AI_LAB_ENFORCEMENT=1
WORKER_TUNNEL_URL=http://127.0.0.1:8765
NVIDIA_SMI_POLL_INTERVAL=5
# Linux: nvidia-smi is usually on PATH. Windows leftover path is not used here.
# NVIDIA_SMI_PATH=/usr/bin/nvidia-smi
WATCH_PATHS=/mnt/workshop/Repos/products/ai-lab:/mnt/workshop/Repos/products/ai-lab-governance
# Compose overrides Windows .env paths with the values in docker-compose.yml.
```

## Testing

Backend tests live in `backend/tests/`. From the backend directory:

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest tests/ -v
```

Frontend tests run from `frontend/`:

```bash
npm test
```

## Diagnostics

- Backend request and event logs are written to `../../logs/command_center/` as JSONL files.
- Tool execution logs from core `brain.execution` continue to write to `../../logs/execution_logs/`.
- Guru thread/audit logs continue to write to `../../logs/guru_threads/` and `../../logs/config_changes/`.
- Browser-side UI diagnostics for API and WebSocket behavior are stored in local storage under `command-center:diagnostics`.

See `../../TESTING.md` for the full test harness (ai-lab core + command-center backend).

## Compute / hardware metrics

If the **Compute** tab shows zeros, “GPU query failed”, or suggests missing `psutil` / `nvidia-smi`:

1. **Backend venv** – Install backend deps (`pip install -r requirements.txt`); `psutil` must be importable by the same Python that runs Uvicorn.
2. **`nvidia-smi`** – Must be runnable by that process. On Windows it is often **not** on `PATH`; set **`NVIDIA_SMI_PATH`** in `backend/.env` to the full path, e.g.  
   `C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe`  
   (see `backend/.env.example`).
3. **Sanity check** – Open `http://localhost:8000/api/hardware/snapshot` (or your API host); `ram_total_gb` should be above zero when `psutil` works; `gpu` should populate when `nvidia-smi` succeeds.
4. **WebSocket replay** – The backend keeps only the latest `hardware` event in history for new subscribers; the UI also avoids replacing a good snapshot with an all-zero fallback.

## Weather & time (no search quota)

- **Weather** in chat is answered with **Open-Meteo** (free, no API key). It does **not** use Tavily/Serper. Set **`WEATHER_CITY`** or **`WEATHER_LAT` / `WEATHER_LON`** in `backend/.env`, or ask e.g. “weather in Austin”.
- **“What time is it?”** uses the **local timezone** from session (`user_timezone`); it does **not** trigger paid web search.

## Architecture

```
Browser ──WS──► EventBus (FastAPI)
                    │
          ┌─────────┼──────────┐
          ▼         ▼          ▼
    SupervisorBridge  NvidiaPoller  RepoWatcher
          │
    ┌─────┴──────┐
    ▼            ▼
  run_approved  Worker API
  log_action    (tunnel :8765)
```

All state-changing actions go through `SupervisorBridge` → `run_approved` / `submit_approval` wrappers only. No direct shell execution from the UI backend.
