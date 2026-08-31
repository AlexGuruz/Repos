# Stage 12 — Browser console (`12_BROWSER_CONSOLE.md`)

**Method limit:** Cursor IDE browser MCP unavailable this session after Stage 3. No fresh DevTools console dump.

## Observed / classified

| Finding | Class |
|---------|-------|
| Stage 3 Chat/Compute tab switches without UI crash | benign |
| Pending badge APR 46 backlog (prior smoke/`UI_*` markers) | known limitation / demo clutter |
| Vite `optimizeDeps.esbuildOptions` deprecation (npm test) | benign |
| npm `Unknown env config "devdir"` | benign |
| Worker health / tunnel offline UI messaging on Compute | demo risk (hard blocker for worker path) |
| Recurring FE critical exceptions | none observed in Stage 3 browsing |
| Dual-connect channel sockets + `/ws/events` | not observed (code path) |
| Backend `growflow_sales_today` script path missing | hard blocker for that tool |
| API multi-second latency under load / large pending queue | demo risk |

## Backend / tunnel / worker logs

- `errors.jsonl` small; no traceback storm recorded in Stage 2 startup files
- Worker assistant: timeout / unreachable throughout qualification
- Tunnel scheduler idle (0 submitted)

## Stage console exit

No recurring critical FE errors proven. **Demo risk / hard blockers** remain on worker + tool path; browser console evidence incomplete.
