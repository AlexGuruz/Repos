# Stage 1 — Clean Environment Evidence

**Date/time:** 2026-07-14 17:42:36 -05:00 (capture start); Stage 1 closed ~2026-07-14 18:07 -05:00  
**Operator machine:** Main rig (`AI_LAB_MACHINE=main` per backend `.env`)  
**Hostname:** Windows 10/11 host at `E:\Repos`

## Stop procedure

```powershell
E:\Repos\ai-lab\command-center\command-center\scripts\stop.ps1
```

Result:
- Port 8000 → stopped PID 54356 (`python`)
- Port 5173 → stopped PID 71568 (`node`)
- Post-stop Listen on **8000 / 5173:** NONE (only TIME_WAIT remnants that cleared)

## Ports after stop

| Port | State | Owning PID | Process | Stack? |
|------|-------|-----------:|---------|--------|
| 8000 | no Listen | — | — | free for qualification |
| 5173 | no Listen | — | — | free for qualification |
| 8765 | Listen (later) | ssh 44692 | OpenSSH | worker tunnel (local forward); **not** healthy assistant |
| 8766 | Listen | ssh 32876 | OpenSSH | secondary worker-node forward (`-L 8766:127.0.0.1:8765`) |

Evidence: `evidence/stage1_ports.txt`

## Processes remaining (not CC)

- `node`: Cursor helpers, Adobe Creative Cloud, Firebase MCP (`npx firebase-tools mcp`) — **not** Vite CC — left running
- No `python`/`uvicorn` CC backend after stop
- No unrelated processes killed

Evidence: `evidence/stage1_node_cmds.txt`

## Scheduled / managed starts (main rig)

| Task | State | Notes |
|------|-------|-------|
| AiLabWorkerTunnel | Ready | Started during Stage 1; result 267009 (running) |
| AiLabAllWorkerTunnels | Ready | Last result 267014 |
| WorkerAssistantTunnel | Ready | Last result 0 |
| Growflow* tasks | Ready | Unrelated; **not** disabled |

Evidence: `evidence/stage1_scheduled.txt`

## Repository state

| Field | Value |
|-------|-------|
| Path | `E:\Repos` (ai-lab under `E:\Repos\ai-lab`) |
| Branch | `main` |
| HEAD | `f91518317d26fe4913b0acabe98c4c29330927a5` |
| Tracking | `main...origin/main` |
| Python | 3.14.2 |
| Node | v24.14.0 |
| `.venv` | Present (`command-center/command-center/.venv`) |
| `backend/.env` | Present (loaded source for CC) |
| `backend/env.minimal` | Present |
| `AI_LAB_MACHINE` | `main` |
| `AI_LAB_ENFORCEMENT` | `1` |
| `AI_LAB_GOVERNANCE_ROOT` | `E:\Repos\ai-lab-governance` |
| `WORKER_TUNNEL_URL` | `http://127.0.0.1:8765` |
| `OPERATOR_DESK_ENABLED` | `1` |
| `CC_LIGHT_MODE` | not set in `.env` (will force `0` at Stage 2) |

### Dirty tree classification (summary)

Working tree is **heavily dirty** (pre-existing ai-lab channel isolation + Growflow/Kylo/docs). Classification:

| Class | Examples |
|-------|----------|
| `pre-existing` | Growflow scripts/docs, Project-Kylo, Obsidian, Power1 scripts |
| `expected` | Channel isolation mods under `ai-lab/command-center/...` (`channels.py`, `events.py`, `feed_bus.py`, WS frontend, tests, DATA_CHANNELS docs) from prior implementation |
| `qualification-created` | `ai-lab/docs/command_center_investor_demo_qualification/**` (this run) |
| `unexplained` | None identified specific to unexpected CC listeners; dirty state is **understood** as pre-existing lab work + expected isolation diffs — **not** a clean-start process interferer |

Full status: `evidence/stage1_git_status.txt`

## Legacy event stream

| File | Size (bytes) | LastWriteTime |
|------|-------------:|---------------|
| `event_stream_20260714_145601.jsonl.archived` | 41,294,184,661 (~39 GB) | 2026-07-14 14:56 |
| `event_stream.jsonl` | 1,160,622 | 2026-07-14 15:49 |

- Function present: `ensure_legacy_event_stream_not_appended` in `backend/services/observability.py`
- Qualification requirement: after Stage 2 startup, re-check that legacy `event_stream.jsonl` mtime does not advance and new traffic goes to channel JSONLs

Evidence: `evidence/stage1_legacy_logs.txt`, `evidence/stage1_legacy_fn.txt`

## Worker tunnel / worker machine

| Check | Result |
|-------|--------|
| SSH to `worker@worker-node` | OK (`hostname` → `worker-node`) |
| `power-1` DNS | **FAIL** — `Could not resolve hostname power-1` (primary-worker docs point here; unavailable) |
| Local `WORKER_TUNNEL_URL` `:8765` | SSH Listen present; HTTP `/health` → **empty reply / closed** |
| Tunnel `:8766` → worker-node:8765 | HTTP `/health` → **empty reply** (no remote listener on 8765) |
| Remote `worker_assistant` import | `import_ok` |
| Remote start attempts | PID started then **no LISTEN on :8765**; health still unavailable |
| Staging scripts used | `ensure_worker_assistant_on_8765.ps1`, qualification `remote_start*.ps1` via SCP |

**Stage 1 status of worker path:** Known and **unhealthy**. Per qualification hard gates, unavailable worker path will force final verdict `NOT READY — BLOCKERS REMAIN` unless recovered before Stages 4–8 complete.

Config: `scripts/worker_tunnel.local.json` → `{ user: worker, workerHost: worker-node }`

## Stage 1 exit criteria

| Criterion | Status |
|-----------|--------|
| Ports 8000 and 5173 free before startup | **PASS** |
| No duplicate CC backend/frontend | **PASS** |
| Repository and environment recorded | **PASS** |
| Worker tunnel status known | **PASS** (known unhealthy) |
| Legacy log status recorded | **PASS** |
| No unexplained process interferer for CC | **PASS** |

**Stage 1: PASS (with recorded worker blocker risk)**

Next: Stage 2 full-stack start with `CC_LIGHT_MODE=0` (do **not** use `start.ps1` light mode).
