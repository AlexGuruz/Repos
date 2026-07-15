# Stage 2 — Full Stack Start / Service Map

**Started:** 2026-07-14 ~18:10 -05:00  
**CC_LIGHT_MODE:** `0` (set in parent env before `run_uvicorn_once.py`; telemetry published count > 0 proves poller active)

## Exact commands

```powershell
# Frontend
cd E:\Repos\ai-lab\command-center\command-center\frontend
npm.cmd run dev
# PID parent 59652; Listen :5173 → node 62316

# Backend (do NOT use start.ps1 light mode)
$env:PYTHONPATH = "E:\Repos\ai-lab"
$env:OPERATOR_DESK_ENABLED = "1"
$env:CC_LIGHT_MODE = "0"
cd E:\Repos\ai-lab\command-center\command-center\backend
..\.venv\Scripts\python.exe ..\scripts\run_uvicorn_once.py
# launcher PID 18292 → Listen :8000 python 61640
```

Evidence: `evidence/stage2_commands.txt`, `evidence/backend_startup.err`, `evidence/stage2_listen.txt`

## Startup verification

| Check | Result |
|-------|--------|
| Traceback loop | None in `backend_startup.err` |
| Reload child | Not used (`reload=False`) |
| Uvicorn | `Application startup complete` / `running on http://127.0.0.1:8000` |
| ChannelHub | Present via `/api/health` → `channels` |
| TunnelScheduler | Present via `/api/channels/metrics` → `tunnel` |
| Hardware poller | **Active** — telemetry `published: 4` within ~seconds of start |
| Prepared-context / coordinator | Started under light=0 (lifespan creates tasks) |
| Legacy `event_stream.jsonl` mtime | Unchanged `2026-07-14 3:49:58 PM` / size 1160622 |
| `GET /api/health` | ok, machine=main |
| `GET /api/channels/metrics` | ok |
| `GET /api/workers/health` | **worker_assistant timeout**; ollama ok via tunnel; `all_ok=false` |

## Service map

| Service | PID | Port | Status | Dependency | Startup command |
|---------|----:|-----:|--------|------------|-----------------|
| Backend | 61640 (launcher 18292) | 8000 | UP | PYTHONPATH=ai-lab | `run_uvicorn_once.py` with `CC_LIGHT_MODE=0` |
| Frontend | 62316 | 5173 | UP | npm | `npm.cmd run dev` |
| Worker tunnel SSH | 32876 / 44692 | 8766 / 8765 | Listen | OpenSSH | scheduled `AiLabWorkerTunnel` etc. |
| Worker assistant (remote) | — | 8765 remote | **DOWN** | worker-node | start attempts failed to bind health |
| Hardware poller | (in-proc) | internal | UP | ChannelHub telemetry | lifespan `nvidia_poll_loop` |
| Prepared-context refresher | (in-proc) | internal | UP (task) | CONTEXT_EXECUTOR | lifespan |
| Repo-index coordinator | (in-proc) | internal | UP (task) | ops channel | lifespan |
| TunnelScheduler | (in-proc) | internal | UP | — | lifespan `tunnel_scheduler.start()` |
| ChannelHub | (in-proc) | internal | UP | — | lifespan `channels.start()` |

## Stage 2 exit criteria

| Criterion | Status |
|-----------|--------|
| Full mode confirmed | **PASS** (telemetry publishing) |
| One backend | **PASS** |
| One frontend | **PASS** |
| Worker path available | **FAIL** (`worker_assistant` unreachable) |
| Health endpoints | **PASS** (API); worker health reports offline |
| Channel metrics | **PASS** |
| Full workloads active | **PASS** (poller proven) |
| No recurring startup error | **PASS** |

**Stage 2: FAIL on worker path** (stack otherwise healthy). Continuing remaining stages for isolation/evidence; hard gate already anticipates NOT READY if worker never recovers.

WS route openers available in code/router: `/ws/control`, `/ws/ops`, `/ws/chat`, `/ws/telemetry`, `/ws/events` (verify Stage 3 in browser).
