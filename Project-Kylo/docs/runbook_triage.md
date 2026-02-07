# Runbook — Triage & Replay

**When new txns appear:** Unmatched items will show in `"{CID} Pending"`.
- Mark `Approved=TRUE` (human action) → promotion process creates a new rules snapshot.
- Replay worker will mark matching pending as `resolved` and move them to matched flow.

**If Pending grows too fast:** Verify token bucket rate (60/min) and batch sizes (500–1000 rows).
