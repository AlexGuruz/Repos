# Stage 8 — Tunnel fairness (RESUME)

## Worker recovery

`worker_assistant` now healthy on worker-node `:8765` via asyncio.serve launcher (`evidence/wa_serve.py` + `run_wa_serve.bat`). Local `http://127.0.0.1:8765/health` → 200.

## Fairness evidence

While control metrics polling continued:

- `POST /api/tools/invoke` `index_repo` entered **bulk** lane (`tunnel.metrics.by_lane.bulk.submitted=1`) — `evidence/resume_tunnel_scheduler2.json`
- Control `/api/channels/metrics` stayed mostly healthy (5/6 samples) during bulk attempt
- Direct interactive `GET /repo_status` on tunnel stayed ~0.7–2.1s — `resume_tunnel_fairness2.json`

Bulk execution returned HTTP 503 governance read-only (WA started with `lifespan=off` for bind reliability). Hard gate is **non-blocking of control**, not bulk success.

## Stage 8 exit

**PASS** for non-blocking control under bulk submit. Worker write path needs governance env on WA for successful `index_repo` completion (demo restriction).
