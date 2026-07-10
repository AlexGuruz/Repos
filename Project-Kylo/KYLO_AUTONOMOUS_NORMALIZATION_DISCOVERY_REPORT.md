# KYLO_AUTONOMOUS_NORMALIZATION_DISCOVERY_REPORT

## 1. Current transaction pipeline

Kylo currently has multiple active/legacy paths:

- **CSV ingest path (global DB first):**
  - Ingest/download: `services/intake/csv_downloader.py` (`download_petty_cash_csv`)
  - Parse/normalize: `services/intake/csv_processor.py` (`PettyCashCSVProcessor.parse_transactions`, `_normalize_description`, `_generate_txn_uid`, `_generate_content_hash`, `_generate_business_hash`)
  - Dedup workflow: `services/intake/deduplication.py` (`DeduplicationWorkflow.process_with_deduplication`)
  - Store raw/unified: `services/intake/storage.py` (`store_csv_transactions_batch`, `_store_with_copy`, `_store_with_batch_insert`)
  - CLI entry: `bin/csv_intake.py` (`process_csv_intake`)

- **Global->company mover path (batch-based):**
  - Service: `services/mover/service.py` (`MoverService.move_batch`)
  - SQL: `services/mover/sql.py` (`SLICE_SQL`, `UPSERT_AND_ENQUEUE_SQL`, `ADVANCE_WATERMARK_SQL`, `EMIT_OUTBOX_SQL`, rules snapshot SQL)
  - Moves `core.transactions_unified` slices into `app.transactions`, enqueues `app.sort_queue`

- **Rule match + pending triage path (Kafka workers):**
  - Consumer: `services/bus/kafka_consumer_txns.py` (`process_message`)
  - Triage: `services/triage/worker.py` (`triage_company_batch`, `_load_active_rules_map`, `_upsert_pending`)
  - Pending post to Sheets: same consumer + `services/sheets/poster.py`

- **Promotion/replay path:**
  - Promote: `services/rules_promoter/service.py` (`promote`)
  - Replay: `services/replay/worker.py` (`replay_after_promotion`)
  - Promote consumer: `services/bus/kafka_consumer_promote.py` (`process_message`)

- **Sheets-first direct posting path:**
  - `services/posting/jgdtruth_poster.py` (`run`, matching/routing/posting logic)
  - Loads rules from Sheets via `services/rules/jgdtruth_provider.py` (`fetch_rules_from_jgdtruth`)

- **Correction/replay handling:**
  - DB replay: `services/replay/worker.py`
  - Sheets-first re-evaluation/skipped-state path: `services/posting/jgdtruth_poster.py` (`rules_changed` flow + skipped txns state)

## 2. Current database model

### Global DB (primary DDL: `db/ddl/0002_core_intake_control.sql`)

- `control.ingest_batches`
  - Keys: `batch_id` PK
  - Mutable: yes (`ended_at`)

- `control.company_feeds`
  - Keys: `company_id` PK
  - Mutable watermark table

- `control.outbox_events`
  - Keys: `id` PK
  - Unique: `ux_outbox_event_key(event_key)` partial
  - Indexes: `(topic, created_at)`
  - Mutable delivery marker

- `intake.raw_transactions`
  - Keys: `ingest_id` PK
  - Unique: `ux_raw_fingerprint(fingerprint)`
  - Indexes: `(company_id, ingest_batch_id)`
  - Mostly append-only raw store

- `core.transactions_unified`
  - Keys: `txn_uid` PK
  - Indexes: `(company_id, updated_at)`, `(company_id, ingest_batch_id)`
  - Mutable upsert target

- `control.company_rules_version`
  - Keys: `company_id` PK
  - Mutable version/checksum state

- `control.rules_activations`
  - Keys: PK `(company_id, activate_at_batch)`
  - Append-style activation scheduling

- `control.mover_runs`
  - Metrics/audit rows

### Additional global dedupe/audit tables (`db/ddl/0008_csv_intake_deduplication.sql`)

- `control.file_processing_log` (file-level dedupe guard)
- `control.deduplication_log` (per-dedup-step metrics)
- `control.deduplication_summary` (aggregate metrics)
- `control.business_duplicates` (potential business dupes)
- Added to `intake.raw_transactions`: `business_hash`, unique index `ux_raw_business_hash`
- Unique index: `ux_raw_file_row(source_file_fingerprint, row_index_0based)`

### Company DB (`db/ddl/company_0001_app.sql`)

- `app.transactions`
  - PK: `txn_uid`
  - Unique: `(source_stream_id, source_file_fingerprint, row_index_0based)`
  - Indexes: `posted_date`, `hash_norm`
  - Mutable

- `app.rules_active`
  - PK: `rule_id`
  - Unique index: `ux_rules_active_rule_hash(rule_hash)`
  - Mutable (truncate/replace)

- `app.sort_queue`
  - PK: `queue_id`
  - Unique: `(txn_uid, reason)`
  - Work queue append-only

- `app.outputs_projection`
  - PK: `txn_uid`
  - Mutable projection table
  - Runtime writers: not found in current service code

- `app.outbox_events`
  - Local outbox table

### Other relevant tables

- `app.pending_txns` (`db/ddl/0011_app_pending_txns.sql`)
- `control.sheet_posts` (`db/ddl/0012_control_sheet_posts.sql`) for posting idempotency
- `control.triage_metrics` (`db/ddl/0013_control_triage_metrics.sql`)
- `control.rules_snapshots` (`db/ddl/0007_control_migrations_and_rules_snapshots.sql`)
- Legacy rules schema (`db/ddl/0001_rules.sql`): `rulesets`, `rules`, `rule_audit`, `active_rulesets` view

## 3. Current normalization logic

Primary normalization-related code:

- `services/common/normalize.py`
  - `normalize_description(raw)`
  - Deterministic regex normalization (lowercase, punctuation removal, whitespace collapse)

- `services/intake/csv_processor.py`
  - `PettyCashCSVProcessor._normalize_description(description)`
  - Used for `business_hash`
  - Deterministic regex-based

- `services/intake/deduplication.py`
  - `DeduplicationWorkflow._normalize_description(description)`
  - Used in business similarity checks

- `services/rules_loader/loader.py`
  - Uses `normalize_description(source)` to produce `source_norm`

- `services/posting/jgdtruth_poster.py`
  - `_normalize_text` and tab normalization helpers (unicode/text cleanup)

Tests:

- `scaffold/tests/unit/test_normalize.py`
- `scaffold/tests/test_importer_normalization.py`

Classification:

- Deterministic: yes
- Regex-based: yes
- Rule-based matching: yes (triage and poster)
- Manual elements: yes (human-maintained rule sheets/pending tabs)

## 4. Current rule system

Rule sources:

- Google Sheets: `services/rules/jgdtruth_provider.py` (`fetch_rules_from_jgdtruth`)
- Pending DB tables loaded/promoted by:
  - `services/rules_loader/loader.py`
  - `services/rules_promoter/service.py`
- Legacy pending-tabs importer: `scaffold/tools/importer.py`

Active vs pending:

- Pending: `rules_pending_{company_slug}` and/or pending tabs in Sheets
- Active: `app.rules_active`

Promotion:

- `services/rules_promoter/service.py` (`promote`) truncates and re-inserts active rules
- Kafka-triggered via `services/bus/kafka_consumer_promote.py`
- Legacy `scaffold/tools/importer.py` path writes to legacy rules tables

Match order/priority:

- `services/triage/worker.py`: exact match on normalized description key (`description_norm in rules_map`)
- `services/posting/jgdtruth_poster.py`:
  - standard exact/trim/case-insensitive lookup
  - relaxed companies: longest substring match over normalized text

Company scoping:

- Rules can be shared or per-company via company column filtering in `jgdtruth_provider.py`

Conflicts:

- Duplicate source keys in in-memory dict generally resolve by last assignment
- Schema mismatch exists between some workers/tests and company DDL (see notes below)

Unmatched behavior:

- `services/triage/worker.py`: unmatched -> `app.pending_txns`, emit `pending.ready`
- `services/posting/jgdtruth_poster.py`: unmatched tracked/skipped in local state and diagnostics

## 5. Human touchpoints

Current manual decisions/maintenance:

- **Normalization pattern tuning:** code/config (`services/common/normalize.py`, csv processor config fields)
- **Merchant naming:** not found as dedicated autonomous component (column exists in schema, usage not found)
- **`company_id` decisions:** source sheet values + parser defaults
- **Category/header mapping:** manually maintained in rules sheets/pending rules
- **Target sheet/tab mapping:** manually maintained in rules (`target_sheet`)
- **Transfer detection:** not found
- **Account mapping:** not found as dedicated module
- **Correction approval:** via `Approved` columns and promotion workflows
- **Rule promotion:** manual/operational via CLI/consumer/service flows

Where these happen:

- Code: parser/matcher/promoter logic
- DB: pending/active rules and metrics tables
- Google Sheets: rules tabs, pending/active operational tabs
- Config: workbook/year routing, matching behavior flags
- Outside app/manual ops: promotion timing and data hygiene decisions

## 6. Existing tests

Relevant tests found:

- Ingestion:
  - `scaffold/tests/test_csv_intake.py`
  - `scaffold/tests/intake/test_sheets_intake_bounded.py`

- Normalization:
  - `scaffold/tests/unit/test_normalize.py`
  - `scaffold/tests/test_importer_normalization.py`

- Deduplication/idempotency:
  - `scaffold/tests/test_importer_idempotency.py`
  - `scaffold/tests/test_csv_intake.py` (row dedupe checks)
  - `scaffold/tests/test_full_workflow_integration.py` (batch signature dedupe check present)

- Rules/matching/triage:
  - `scaffold/tests/test_importer_validation.py`
  - `scaffold/tests/test_importer_integration.py`
  - `scaffold/tests/triage/test_triage_unmatched_to_pending.py`
  - `scaffold/tests/triage/test_triage_edge_cases.py`

- Routing/mover/outbox:
  - `scaffold/tests/mover/test_mover_watermark_outbox.py`
  - `scaffold/tests/mover/test_watermark_outbox.py`
  - `scaffold/tests/mover/test_copy_path.py`
  - `scaffold/tests/mover/test_rules_snapshot.py`

- Posting:
  - `scaffold/tests/sheets/test_poster.py`
  - `scaffold/tests/posting/test_source_tab_fill.py`

Pass/fail status in this environment:

- Could not run due to missing dependency: `psycopg2` (`ModuleNotFoundError`)
- Status: not determined

## 7. Integration boundaries

- **Google Sheets source files**
  - CSV export and/or values API reads
  - `services/intake/csv_downloader.py`, `services/posting/jgdtruth_poster.py`, `services/rules/jgdtruth_provider.py`

- **Google Sheets target files**
  - `batchUpdate` and append operations
  - `services/sheets/poster.py`, `services/posting/jgdtruth_poster.py`, consumers

- **Service accounts**
  - Loaded in `services/sheets/poster.py`, `services/intake/csv_downloader.py`, `services/rules_loader/sheets_loader.py`

- **Batch posting mechanics**
  - Broad use of `spreadsheets().batchUpdate(...)`
  - Some append path: `_ensure_transactions_append` in `services/posting/jgdtruth_poster.py`

- **APIs/queues/webhooks/workers**
  - Kafka consumers: `services/bus/kafka_consumer_txns.py`, `services/bus/kafka_consumer_promote.py`
  - Webhook API: `services/webhook/server.py`
  - Poll-based listener: `services/rules/listener.py`
  - n8n workflow JSON configs under `workflows/n8n/`

Per-row/single-cell patterns:

- Found cell-level projection logic in `services/posting/jgdtruth_poster.py` (builds many fine-grained writes, grouped into batchUpdate)
- No explicit one-HTTP-call-per-cell loop found in reviewed code; batching is used

## 8. Best insertion points for autonomous normalization

Safest recommendation (based on current code):

- Insert autonomous normalization as a **sidecar suggestion engine** for unmatched items, not as a replacement for canonical hashing keys initially.

Preferred insertion points:

1. **After triage unmatched creation (`app.pending_txns`)**
   - Hook near `services/triage/worker.py` after unmatched list is produced
   - Benefits: no risk to ingest dedupe/idempotency keys

2. **Shadow-mode in Sheets-first poster path**
   - In `services/posting/jgdtruth_poster.py`, run classifier on no-rule matches and emit suggestions only

3. **Batch clustering worker over unmatched**
   - Separate worker consuming pending/open transactions for candidate rule generation

Avoid as first step:

- Replacing/rewriting description before `txn_uid/hash_norm/fingerprint` generation in intake path (high blast radius)

## 9. Safety constraints for proposed design

Must not break:

- **Idempotency**
  - `control.outbox_events.event_key` uniqueness
  - `control.sheet_posts.batch_signature` behavior
  - queue dedupe (`app.sort_queue` unique constraints)

- **Dedupe keys**
  - `intake.raw_transactions.fingerprint`
  - `business_hash` behavior if enabled
  - `hash_norm` semantics in upserts

- **Audit trail**
  - dedupe logs/summaries
  - triage metrics
  - rules snapshots and audit tables

- **Correction/replay**
  - `services/replay/worker.py` logic depends on stable normalized keys
  - skipped/resume state in `services/state/store.py`

- **Google Sheets pointers/state**
  - `compute_cell_key`, `compute_signature`, persisted state format

- **batchUpdate posting behavior**
  - request composition and tab/header assumptions

- **Company isolation**
  - DSN routing and company filters throughout mover/triage/posting flows

- **Production data integrity**
  - Resolve schema drift before deep integration (triage/replay vs company DDL shape mismatch)

## 10. Files ChatGPT should review first (priority 10-20)

1. `services/posting/jgdtruth_poster.py`
   - Why: largest live routing/matching/posting logic
   - Functions: `run`, internal `_process_target`, `_normalize_text` helpers

2. `services/intake/csv_processor.py`
   - Why: transaction parsing and hash identity generation
   - Functions/classes: `PettyCashCSVProcessor`, `_generate_txn_uid`, `_generate_business_hash`, `_normalize_description`

3. `services/intake/storage.py`
   - Why: raw/unified persistence and conflict strategy
   - Functions: `store_csv_transactions_batch`, `_store_with_copy`, `_store_with_batch_insert`

4. `services/mover/service.py`
   - Why: global->company replication and event emission
   - Functions/classes: `MoverService.move_batch`

5. `services/mover/sql.py`
   - Why: authoritative operational SQL for upsert/enqueue/watermark/rules snapshot
   - Symbols: `UPSERT_AND_ENQUEUE_SQL`, `ADVANCE_WATERMARK_SQL`, rules snapshot SQL constants

6. `services/triage/worker.py`
   - Why: unmatched handling and rule matching surface
   - Functions: `triage_company_batch`, `_load_active_rules_map`, `_upsert_pending`

7. `services/replay/worker.py`
   - Why: correction/replay behavior after promotions
   - Function: `replay_after_promotion`

8. `services/common/normalize.py`
   - Why: shared description normalization primitive
   - Function: `normalize_description`

9. `services/rules/jgdtruth_provider.py`
   - Why: active rules ingestion from Sheets
   - Functions/classes: `fetch_rules_from_jgdtruth`, `Rule`

10. `services/rules_promoter/service.py`
    - Why: promotion mechanics and snapshots
    - Functions: `promote`, `_fetch_pending_approved`, `_apply_snapshot_to_company`

11. `services/bus/kafka_consumer_txns.py`
    - Why: operational orchestration of mover+triage+pending post
    - Function: `process_message`

12. `services/bus/kafka_consumer_promote.py`
    - Why: promote/replay + Active-tab refresh integration
    - Function: `process_message`

13. `services/sheets/poster.py`
    - Why: tab creation, pending batch update builders, service account handling
    - Functions: `_get_service`, `ensure_company_tabs`, `build_pending_batch_update`

14. `services/state/store.py`
    - Why: posting idempotency and skipped txn state
    - Functions/classes: `State`, `compute_cell_key`, `compute_signature`, `load_state`, `save_state`

15. `scaffold/tools/importer.py`
    - Why: legacy but important pending->active promotion path
    - Functions: `importer_run`, `normalize_row`, `stable_hash`

16. `services/rules_loader/loader.py`
    - Why: pending rules loading and `source_norm` generation
    - Functions: `_row_to_pending`, pending table helpers

17. `services/intake/deduplication.py`
    - Why: dedupe strategy and metrics model
    - Class: `DeduplicationWorkflow`

18. `db/ddl/0002_core_intake_control.sql`
    - Why: global canonical schema

19. `db/ddl/company_0001_app.sql`
    - Why: company schema and queue/output tables

20. `db/ddl/0008_csv_intake_deduplication.sql`
    - Why: dedupe and business duplicate tracking constraints

## Notes / not found

- `app.outputs_projection` writers in current runtime code: not found
- Dedicated transfer detection module: not found
- Dedicated account mapping module: not found
- Test execution status in this environment: not determined (missing `psycopg2`)
