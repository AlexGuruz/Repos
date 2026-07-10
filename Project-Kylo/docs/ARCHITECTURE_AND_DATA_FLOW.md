# Kylo Technical Architecture & Data Flow

**Updated:** 2026-07-10

---

## Architecture overview

Kylo is a **multi-company petty-cash automation system** that:

1. Reads transactions from **year-routed Google Sheets intake workbooks** (TRANSACTIONS, BANK).
2. Matches them against **JGDTruth rules** (management workbook or DB snapshot).
3. Projects **aggregated amounts** into target financial workbook cells (tab × header × date).
4. Uses **incremental signatures** to avoid rewriting unchanged cells.
5. Runs an optional **forensic audit** path that snapshots and diffs intake without posting.

### Workbook separation (implemented)

| Workbook | Purpose |
|----------|---------|
| Rules Management | Pending/Active rule tabs per company |
| Company / year transaction workbooks | Intake + financial output tabs |

See `docs/sheets_contract.md` and `docs/WORKSHEET_ARCHITECTURE.md`.

---

## Config layering (implemented)

```
config/global.yaml
  → config/companies/<CID>.yaml (optional)
    → config/instances/<INSTANCE_ID>.yaml
      → clients/<id>/config.yaml (optional overlay)
```

Activated when `KYLO_INSTANCE_ID` is set and `global.yaml` exists (`services/common/config_loader.py`).

Legacy single-file: `config/kylo.config.yaml` (used when no instance id).

---

## Instance model (implemented)

| Instance | Active years | Companies |
|----------|--------------|-----------|
| KYLO_2025 | 2025 | NUGZ, EMPIRE, PUFFIN, JGD |
| KYLO_2026 | 2026 | Same |
| JGD_2025 / JGD_2026 | Per-file | JGD only |

State isolation: `.kylo/instances/<INSTANCE_ID>/state/`

---

## 35-step processing flow

### Phase A — Watcher tick (orchestration)

1. Parse CLI / env (`--instance-id`, `--years`, `--once`)
2. Load layered config; validate schema
3. Resolve companies list (optionally single-company instance)
4. Load `watch_state.json` per instance
5. **Audit tick** (`run_audit_tick`) if audit enabled
6. Load intake via audit loader or csv path
7. Compute per-company rules checksum
8. Compute per-company intake checksum
9. Compare to previous ack → `change_detected`
10. Evaluate gates: `audit_mode`, `KYLO_READ_ONLY`, `posting.sheets.apply`, circuit breaker

### Phase B — Rule matching & projection

11. Load transactions for target company/year
12. Load active rules (JGDTruth provider)
13. For each transaction: normalize source, amount, date
14. Match rule by source pattern
15. Resolve target tab via workbook title map
16. Append to `matched_writes` with `for_marking = not is_posted`
17. Build `pending_writes` subset for mark/notes only
18. Batch-read header row for touched tabs
19. Aggregate `cell_totals` from **all** matched_writes
20. Track `cell_txns` + `cell_source_tabs` per A1 cell
21. Build per-tab Column A date map (canonical M/D/YY)
22. Resolve static date row → actual row (off-by-one correction)
23. Compute SHA-256 **cell signature** (sorted txn_uids + total cents)

### Phase C — Incremental post

24. Load `posting_state.json` signatures
25. Skip cells where signature unchanged (unless baseline / rules_changed)
26. Optional verify mode: read skipped cells from sheet
27. Build `batchUpdate` payload for changed cells only
28. Evaluate `dry_run` (env + config)
29. Execute `values.batchUpdate` on target workbook (if not dry)
30. Apply `source_tab_fill` background colors (optional)
31. Verify unwritten ranges before mark (if `mark_posted`)
32. Repair verified-bad ranges
33. Mark intake Column F + notes (if `mark_posted` enabled)
34. Persist new signatures + processed_txn_uids
35. Return summary; watcher updates ack + heartbeat

---

## Optional Kafka pipeline (planned / parallel)

```
Webhook/n8n ingest → Kafka txns topic → consumer → mover → triage → poster
Rules promote → Kafka promote topic → rules_promoter
```

See `docs/KAFKA_EVENT_BUS_RUNBOOK.md`, `docs/workflow.md`.

---

## Data stores

| Store | Path / DB | Purpose |
|-------|-----------|---------|
| Watch state | `.kylo/instances/<id>/state/watch_state.json` | Checksum ack |
| Posting state | `.kylo/instances/<id>/state/posting_state.json` | Cell signatures |
| Audit registry | `.kylo/instances/<id>/state/row_registry.json` | Forensic diff |
| Snapshots | `.kylo/instances/<id>/snapshots/` | CSV per tick |
| PostgreSQL | `kylo_global` + per-company DBs | Mover/triage path |
| Kafka | Redpanda | Event bus (optional) |

---

## Key modules

| Module | Responsibility |
|--------|----------------|
| `kylo/watcher_runtime.py` | Main loop, gates, audit+post orchestration |
| `services/posting/jgdtruth_poster.py` | Match, project, write, mark |
| `services/audit/tick.py` | Forensic snapshot/diff |
| `services/rules/jgdtruth_provider.py` | Rule source abstraction |
| `services/intake/csv_processor.py` | Sheet → txn objects |
| `services/state/store.py` | Signature persistence |
| `services/mover/service.py` | DB replication (batch path) |
| `services/triage/worker.py` | Unmatched → pending queue |

---

## Status legend

| Label | Meaning |
|-------|---------|
| **Implemented** | In production code path today |
| **Planned** | Documented, not required for JGDTruth watcher path |
| **Deprecated** | Do not use for new work |
