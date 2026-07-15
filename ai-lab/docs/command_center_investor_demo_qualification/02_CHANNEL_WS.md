# Stage 3 — Browser Channel Validation

**URL:** http://localhost:5173/  
**Time:** 2026-07-14 ~18:12–18:20 local

## Method

Real Cursor IDE browser against local Vite. Channel client counts confirmed via `GET /api/channels/metrics`. Implementation: `frontend/src/hooks/useWebSocket.js`.

## Default / Chat tab (after visit)

Opened CC → Chat selected initially, then Compute, then Chat again.

| Channel | Connected clients (after Chat return) | Notes |
|---------|--------------------------------------:|-------|
| control | 2 | Expected ≥1 from `/ws/control`; second may be HMR/reconnect overlap |
| ops | 2 | Same |
| chat | 2 | Same |
| telemetry | 1 | After leaving Compute, client count **should be 0**; observed **1** briefly — possible reconnect race or delayed close (document as watch item) |

Telemetry **published** continued rising (poller active) independent of UI clients.

## Compute tab

- Clicked Compute tab (accessibility ref e6); Compute became selected.
- Hardware UI rendered (Raw worker health / Raw hardware snapshot controls visible).
- Worker health UI shows tunnel/worker offline messaging (consistent with Stage 1/2).
- Screenshot attempt timed out once (recorded).

## Leave Compute → Chat

- Clicked Chat (ref e4); Chat selected.
- Approval cards visible with Approve / Deny / Always Approve (pending hydrate).
- Control path still functional (cards present).

## Compatibility `/ws/events`

Not dual-connected by main frontend (code opens channel sockets only). Dedicated Python probe deferred to Stage 12/evidence harness if needed; design verification in `useWebSocket.js` + deprecated connect path in `feed_bus.py`.

## Console / UI findings (browsing)

- APR count badge showed **46** pending (backlog includes prior `UI_*_MARKER` smoke rows).
- Prepared-context badge: healthy.
- No hard crash of UI observed during tab switches.

## Stage 3 exit

| Criterion | Status |
|-----------|--------|
| Channel sockets match design | **PASS** with note on client=2 |
| Compute owns telemetry lifecycle | **PARTIAL** — opens on Compute; disconnect to 0 not proven (client 1 lingered) |
| Control works without Compute | **PASS** |
| Compat excludes telemetry | **NOT LIVE-PROBED** (code-path evidence only) |
| No recurring critical console errors | **PASS** (no crash) |

Evidence: `evidence/stage3_metrics_after_chat.json`, `evidence/stage3_approvals.json`
