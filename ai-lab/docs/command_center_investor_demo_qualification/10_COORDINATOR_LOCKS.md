# Stage 11 — Coordinator locks

**File:** `backend/services/repo_index_coordinator.py`

## Review table

| Location | Lock | Protected data | Disk work | Observed duration | Control impact | Action |
|----------|------|----------------|-----------|-------------------|----------------|--------|
| `stop()` | `async with self._lock` | full `_states` | `_persist_state()` → `RepoIndexStateStore.save` | Not timed live | None observed | post-beta debt |
| `_tick` classify path | holds lock across classify + `_persist_state()` | per-repo state | sync disk save under lock | Not timed live | None observed (worker bulk idle) | post-beta debt |
| Other handlers (~L288–698) | same pattern | state mutations | `_persist_state()` under lock | Not timed live | None | no live fix |

## Live impact

No investor-path control stall attributed to coordinator persist during this run (tunnel bulk idle; worker down). Plan: **minimal fix only if live evidence shows stall** → **no code change**.

## Stage 11 exit

**PASS as debt** — documented; not an investor-demo blocker without live impact evidence.
