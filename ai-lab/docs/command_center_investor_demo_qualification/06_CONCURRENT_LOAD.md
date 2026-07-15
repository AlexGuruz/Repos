# Stage 7 — Concurrent load

**Harness:** `evidence/qual_stage7_load_harness.py` (25s, slow `/ws/telemetry` client lag 250ms + API pressure)  
**CC_LIGHT_MODE:** 0 (full stack from Stage 2)

## Metrics summary

| Signal | Before | After | Gate |
|--------|-------:|------:|------|
| control.dropped | 0 | 0 | **PASS** — 0 silent control drops |
| control.overload | 0 | 0 | PASS |
| telemetry.published | 302 | 305 | poller active |
| telemetry.send_failures | 0 | 1 | watch (slow client) |
| tunnel submitted | 0 | 0 | no bulk in this stage |

Evidence: `stage7_metrics_before.json`, `stage7_metrics_during.json`, `stage7_metrics_after.json`, `stage7_summary.json`

## Latencies

| Metric | Value | Note |
|--------|------:|------|
| Harness API loop p95 | ~15951 ms | Only 3 iterations/25s — event-loop/API contended (large approval queue / worker health timeouts) — **not** control-publish measure |
| QUAL Approve publish_ms | 0–250 ms | From `resolve_result` for approval-103/105 (`stage4_6_api_tail.jsonl`) |
| QUAL Approve total_ms | 858–4983 ms | Includes pending lookup under load |

### Control publish gate (p95 < 500 ms)

Measured `publish_ms` on real Approve resolutions: **0** and **250** ms → **under 500 ms**.  
Harness wall-clock API latency was dominated by other work — reported separately; does not redefine control gate.

Browser→worker RT: **not met** (tool exec failed; worker down) — report as downstream FAIL independently.

## Incomplete vs plan ideal load

- ~50 Hz *synthetic* in-process publish: **not** injected live (harness used real poller + slow WS client only).
- Repo-path ops bursts / bulk tunnel ops: deferred Stage 8 (worker bulk impossible).
- Repeating real browser Approve/Deny under load: **not** done (browser MCP unavailable).

## Stage 7 exit

**PARTIAL / FAIL for demo** — control drops 0; publish_ms samples <500ms; live synthetic 50Hz + browser concurrent Approve not fully executed; system under stress shows multi-second API latency (demo risk).
