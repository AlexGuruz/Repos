# Frontend–backend contract audit

**Goal:** Ensure every UI panel accurately reflects the data currently exposed by the backend.  
**Source of truth:** Backend routes and WebSocket event payloads.

---

## 1. Source-of-truth matrix

| UI Surface | Frontend File | Data Source | Backend Endpoint/Event | Expected Fields | Actually Rendered | Drift |
|------------|---------------|-------------|------------------------|-----------------|-------------------|--------|
| Compute Panel (hardware) | ComputePanel.jsx | REST + WS | GET /api/hardware/snapshot, WS hardware | gpu, cpu_percent, ram_used_gb, ram_total_gb, timestamp, cpu, node | gpu, cpu_percent (or cpu.total_usage_percent), ram_*, timestamp, node/cpu freq/temp as sub, snapshot time | **Accurate** |
| Compute Panel (worker) | ComputePanel.jsx | REST | GET /api/workers/health | worker_name, ssh_configured, all_ok, services[], tunnel_status, last_checked, error | All of the above | **Accurate** |
| Tools Panel | ToolsPanel.jsx | REST | GET /api/tools/stats | toolCalls[], dataMovement[] | toolCalls (tool, orch, worker, rag, sup), dataMovement (op, cls, vol, pct, calls) | **Accurate** (backend placeholder) |
| Repo Panel (tree) | RepoPanel.jsx | REST | GET /api/repo/tree | tree[], note | tree (type, path, name, size_bytes, mtime), note | **Accurate** |
| Repo Panel (summaries) | RepoPanel.jsx | REST | GET /api/repo/summaries | summaries[]: name, path, entrypoints | name, entrypoints | **Partial** — path not rendered |
| Feed Panel | FeedPanel.jsx | WS | feed, action, approval, approval_resolution, repo | timestamp, agent, op, detail, bytes | All used | **Accurate** |
| Chat Panel | ChatPanel.jsx | REST + WS | POST /api/chat, GET /api/approvals, WS approval | reply text, apr_id, response_time_ms; approvals[] | messages, pendingApprovals | **Partial** — WS "chat" not consumed (reply comes from REST only) |
| Event store (approvals) | store/index.js, ChatPanel | REST + WS | GET /api/approvals, WS approval, approval_resolution | id, type, agent, action, detail, status, timestamp | All used | **Accurate** |
| WebSocket handler | useWebSocket.js | WS | action, approval, approval_resolution, hardware, feed, repo | event + data | action, approval, approval_resolution, hardware, feed, repo | **Partial** — chat, hardware_alert not handled |
| Guru Panel | GuruPanel.jsx | REST | GET /api/guru, GET /api/guru/{mode}, POST message/confirm/revert | snapshot.modes, current_draft, last_saved_summary, current_rules | Store hydrates; all used | **Accurate** |

---

## 2. Backend response shapes (current code)

### GET /api/hardware/snapshot
- **From brain:** gpu (legacy), cpu_percent, ram_used_gb, ram_total_gb, timestamp, cpu, node
- **Fallback (nvidia_poller):** gpu, cpu_percent, ram_used_gb, ram_total_gb, timestamp

### GET /api/workers/health
- worker_name, ssh_configured, all_ok, services[] (name, ok, url, status_code, detail, latency_ms), tunnel_status (worker_name, expected_ports, reachable_ports, missing_ports, likely_up, detail), last_checked, error?

### GET /api/repo/tree
- tree[]: { type, path } or { type, name, path, size_bytes, mtime }, note

### GET /api/repo/summaries
- summaries[]: { name, path, entrypoints }

### GET /api/tools/stats
- toolCalls[] (tool, orch, worker, rag, sup), dataMovement[] (op, cls, vol, pct, calls)

### GET /api/approvals
- [{ id, type, agent, action, detail, status, timestamp }]

### WebSocket events (event + data)
- **feed:** agent, op?, detail, timestamp
- **chat:** role, text, timestamp, response_time_ms
- **approval:** id, type, agent, action, detail, status, timestamp
- **approval_resolution:** id, resolution, status
- **action:** id, type, agent, op, detail, status, timestamp
- **hardware:** same shape as /api/hardware/snapshot (gpu, cpu_percent, ram_*, timestamp, cpu?, node?)
- **hardware_alert:** alerts[], snapshot, timestamp
- **repo:** path, op, agent

---

## 3. Drift summary

| Area | Status | Notes |
|------|--------|--------|
| Compute (worker) | Accurate | tunnel_status, last_checked, ssh_configured, latency_ms, error all rendered |
| Compute (hardware) | Accurate | cpu, node from backend not rendered; store doesn’t keep them |
| Tools | Accurate | Contract matches; backend currently returns empty arrays |
| Repo | Accurate | summaries.path shown in chips (truncated + title) |
| Feed | Accurate | Lines get timestamp, agent, op, detail from events |
| Chat / approvals | Accurate | REST reply + approval list; approval events consumed |
| WS: chat | Accurate | Backend publishes "chat"; frontend doesn’t handle it (reply comes from REST) |
| WS: hardware_alert | Accurate | Backend publishes "hardware_alert"; frontend doesn’t handle it |

---

## 4. Fixes applied (this audit)

| File | Change |
|------|--------|
| `docs/FRONTEND_BACKEND_CONTRACT_AUDIT.md` | **Created.** Source-of-truth matrix, backend shapes, drift summary, re-audit steps. |
| `frontend/src/hooks/useWebSocket.js` | Import `useChatStore`. Handle `chat`: call `addChatMessage({ role, text, response_time_ms })` and `addLine` for feed. Handle `hardware_alert`: `addLine` with alerts summary. |
| `frontend/src/components/ComputePanel.jsx` | Dev-only: `lastHardwareSnap` state, collapsible raw payloads. **Backend alignment:** use store `cpu`, `node`, `timestamp`; metric row “cpu · main rig” sub shows node or cpu frequency/temp; snapshot time line when present; worker block shows `ssh_configured` (SSH: yes/no). |
| `frontend/src/components/RepoPanel.jsx` | Summaries chips: show `s.path` (truncated), add `title={s.path \|\| s.name}` on chip. |
| `frontend/src/store/index.js` | Hardware store: add `cpu`, `node`, `timestamp` to state and to `update(snap)` so frontend reflects full backend snapshot. |

---

## 5. How to re-audit

1. List every panel and store and the endpoint/event it uses (this doc).
2. From backend: router → response shape; from frontend: API call → store → render.
3. Mark accurate / partial / stale / broken.
4. Fix adapters and renderers; add dev-only raw payload blocks where useful.

**Note:** After the "finish frontend alignment" pass, Compute (hardware) and WS rows are accurate: store keeps cpu/node/timestamp and UI shows them; useWebSocket handles `chat` and `hardware_alert`.
