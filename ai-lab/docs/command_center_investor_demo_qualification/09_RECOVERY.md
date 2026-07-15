# Stage 10 — Recovery

## Covered during qualification

| Scenario | Result | Evidence |
|----------|--------|----------|
| Duplicate resolve after terminal | Typed fail `not found`; no corruption | `stage5_resolve_after_terminal.json` |
| Missing ID | `ok=false`, resolve_timing found=false | Stage 7 harness `approval-missing-qual-*` + prior smoke logs |
| Pending → Approve persists | Decision survives in `resolved_*.json` | `resolved_approval_103.json` |
| Permanent rule on disk | `PAR-9453975B` in `permanent_approvals.json` | Stage 6 |
| Pre-approve execute without resolve | Not observed | — |

## Not fully executed (blocked / deferred)

| Scenario | Status |
|----------|--------|
| CC restart empty / with pending | **NOT RUN** (would interrupt remaining stages; worker already failing) |
| Worker restart mid-pending | **BLOCKED** — worker never healthy |
| Frontend refresh with pending → resolve | **NOT RUN** — browser MCP unavailable |
| Interrupt one channel WS; others stay | **PARTIAL** Stage 3 tab switches only |
| Restart proves PAR survives reload | **NOT RUN** (disk present ≠ process reload proof) |

## Stage 10 exit

**FAIL / INCOMPLETE** relative to plan checklist. Safe duplicate/missing-ID paths OK; restart/WS reconnect matrix not closed.
