# Stage 9 — Logging isolation

**Log root:** `E:\Repos\ai-lab\logs\command_center\`  
Evidence sizes: `evidence/stage9_log_sizes.txt`

## Writers / files

| File | Size (bytes) | Notes |
|------|-------------:|-------|
| control.jsonl | ~13 KB | Small vs ops; updated during Approve/Deny |
| ops.jsonl | ~93 KB | Present; independent file |
| chat.jsonl | 256 | Quiet |
| api_requests.jsonl | ~1.2 MB | Shared API audit (not channel event stream) |
| errors.jsonl | ~8 KB | |
| telemetry.jsonl | **absent** | Hardware ticks not flooding a telemetry JSONL (as designed) |
| event_stream.jsonl | 1,160,622 | **mtime unchanged** since Stage 2 start (15:49:58) — no new appends |

## Legacy

`ensure_legacy_event_stream_not_appended` recorded Stage 1; live mtime stability confirms no append under qualification load. Archive `event_stream_*.jsonl.archived` ~39 GB left untouched.

## Rotation proof

Live temporary `CC_JSONL_MAX_BYTES` shrink + restart **not executed** (would require bouncing full-mode stack mid-qualification with unhealthy worker). Unit coverage remains in `tests/test_observability_channels.py`. **Live rotation under approval traffic: NOT PROVEN.**

## Stage 9 exit

**PASS** for per-channel files + legacy untouched + control stays small.  
**PARTIAL** — rotation live proof skipped.
