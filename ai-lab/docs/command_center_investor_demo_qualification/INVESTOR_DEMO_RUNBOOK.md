# Investor Demo Runbook — Command Center

Supersedes operational start guidance in `docs/command_center_approval_repair/07_DEMO_RUNBOOK.md` for **controlled investor demos**. Keep the older file for historical repair notes.

## Before you start

| Item | Requirement |
|------|-------------|
| Machines | Operator (main) + reachable worker with `worker_assistant` on remote :8765 |
| Commit | Record `git rev-parse HEAD`; avoid unexplained dirty listeners |
| Clean stop | `command-center\scripts\stop.ps1`; confirm **8000/5173 free** |
| Light mode | **`CC_LIGHT_MODE=0`** (or unset). Do **not** use `scripts/start.ps1` (forces light=1) |
| Env | `OPERATOR_DESK_ENABLED=1`, `WORKER_TUNNEL_URL=http://127.0.0.1:8765`, `PYTHONPATH=E:\Repos\ai-lab` |
| Tunnel | `ai-lab\scripts\start_worker_tunnel.ps1` (or scheduled AiLabWorkerTunnel); prove `curl http://127.0.0.1:8765/health` |
| Auth | Local loopback demo; no extra auth assumed |

### Full-mode start (record exact commands)

```powershell
# Worker tunnel first — must be healthy
# Then backend (ONE process, no --reload):
$env:PYTHONPATH = "E:\Repos\ai-lab"
$env:OPERATOR_DESK_ENABLED = "1"
$env:CC_LIGHT_MODE = "0"
cd E:\Repos\ai-lab\command-center\command-center\backend
# IMPORTANT: run_uvicorn_once.py setdefaults light=1 — set CC_LIGHT_MODE=0 BEFORE invoking
..\.venv\Scripts\python.exe ..\scripts\run_uvicorn_once.py

# Frontend:
cd E:\Repos\ai-lab\command-center\command-center\frontend
npm.cmd run dev
# URL: http://localhost:5173
```

### Prove services

- `GET /api/health` → ok; channels present  
- `GET /api/channels/metrics` → TunnelScheduler + ChannelHub; telemetry published rising if poller live  
- `GET /api/workers/health` → `all_ok` ideally; **worker_assistant must be ok** for demo  
- Expected WS (Chat): `/ws/control`, `/ws/ops`, `/ws/chat` — **not** full-rate `/ws/telemetry` until Compute tab

## Demo flow (safe / repeatable)

1. Health + worker ok  
2. Open Compute → confirm telemetry; leave Compute → control still works  
3. Propose real allowlisted tool via Operator Desk (`POST /api/operator/actions:propose`) — must yield **`approval-N` + `tool_name`**  
4. Chat: **Approve** → card clears; control shows action; **tool runs successfully once**  
5. New card: **Deny** → no execute; later approve no-ops  
6. Scoped **Always Approve** → `PAR-*` in `state/permanent_approvals.json`; restart CC; matching auto-path (orchestrator/supervisor); Operator Desk re-propose currently may still queue — verify intended path before camera  
7. Audit: `logs/approval_logs/resolved_*.json`, channel JSONLs, metrics  
8. Optional: start safe bulk (`index_repo`) + interactive/control health — neither waits for bulk end  
9. Clean stop via `stop.ps1`

## Recovery notes

- Duplicate resolve / missing ID → typed error, no crash  
- After CC restart with pending: resolve normally; do not pre-approve execute  
- Worker restart mid-pending: ensure no double execute before resuming demo  

## Demo restrictions (hard)

- **Do not** treat supervisor **`APR-*`** cards as the browser→worker execution path (dismiss-only / stub)  
- Do not demo with **`CC_LIGHT_MODE=1`** or `start.ps1` light stack  
- Do not demo with unreachable worker / empty tunnel health — prove `curl http://127.0.0.1:8765/health`  
- Prefer **`cc_investor_demo_ping`** for Approve/Deny/Always camera path; avoid deprecated `growflow_sales_today`  
- Start worker_assistant with asyncio launcher (`wa_serve.py` / `run_wa_serve.bat`) if bare `uvicorn` hangs pre-bind  
- `index_repo` write requires WA governance env (otherwise 503 read-only)  
- No stubs, experimental destructive tools, or unfinished features on camera  
- Clear large pending approval backlog before investor session (noise badge)

## Evidence

Qualification pack: `docs/command_center_investor_demo_qualification/`  
Verdict: see `FINAL_QUALIFICATION_REPORT.md`
