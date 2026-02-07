## DB DDL

This folder contains Postgres DDL for rules, the global two‑phase ingest model, and per‑company schemas.

### Files
- `ddl/0001_rules.sql` — Global rules tables (ENUM, tables, indexes, view) in `public`
- `ddl/0002_global_two_phase.sql` — Global DB schemas `intake`, `core`, `control` with:
  - `control.ingest_batches` (strictly monotonic `batch_id`)
  - `control.company_feeds` (per‑company `last_batch_id` watermark)
  - `control.outbox_events` (with `event_key` for idempotency)
  - `intake.raw_transactions` (immutable, fingerprint dedupe)
  - `core.transactions_unified` (normalized, deduped; UUIDv5 `txn_uid`, canonical `hash_norm`)
- `ddl/0003_helpers.sql` — Helpers: UUIDv5 namespace (`kylo://txn`), `sha256_hex`, and `hash_norm_txn(...)`
- `ddl/company_0001_app.sql` — Per‑company DB `app` schema: `transactions`, `rules_active`, `sort_queue`, outputs, outbox
- `ddl/company_0003_rules_snapshot_apply.sql` — Company DB function `app.apply_rules_snapshot(jsonb)` and `app.rules_active_checksum` view
- `ddl/0004_control_rules_version.sql` — Global control table for rules activations/snapshots
- `ddl/0005_control_mover_runs.sql` — Optional per-company slice metrics (observability)
- `ddl/0007_control_migrations_and_rules_snapshots.sql` — Global `control.migrations` ledger and `control.rules_snapshots` store (idempotent)
- `apply.ps1` — simple apply script using `psql` and `DATABASE_URL`

### Apply
```powershell
Set-Location D:\REMODEL\db
./apply.ps1  # uses $env:DATABASE_URL
```

Or explicitly:
```powershell
./apply.ps1 -ConnectionString "postgresql+psycopg2://user:pass@host:5432/dbname"
```

Apply a specific DDL file:
```powershell
./apply.ps1 -ConnectionString $env:DATABASE_URL -File "ddl/0002_global_two_phase.sql"
```

Common sequence (Docker example shown using container `kylo-pg`):
```powershell
# Global DB (once)
docker exec kylo-pg createdb -U postgres kylo_global
docker cp db/ddl/0002_global_two_phase.sql kylo-pg:/
docker exec kylo-pg psql -U postgres -d kylo_global -f /0002_global_two_phase.sql
docker cp db/ddl/0007_control_migrations_and_rules_snapshots.sql kylo-pg:/
docker exec kylo-pg psql -U postgres -d kylo_global -f /0007_control_migrations_and_rules_snapshots.sql

# Company DB (per company; example NUGZ)
docker exec kylo-pg createdb -U postgres kylo_company_nugz
docker cp db/ddl/company_0001_app.sql kylo-pg:/
docker exec kylo-pg psql -U postgres -d kylo_company_nugz -f /company_0001_app.sql
docker cp db/ddl/company_0002_rules_hash.sql kylo-pg:/
docker exec kylo-pg psql -U postgres -d kylo_company_nugz -f /company_0002_rules_hash.sql
docker cp db/ddl/company_0003_rules_snapshot_apply.sql kylo-pg:/
docker exec kylo-pg psql -U postgres -d kylo_company_nugz -f /company_0003_rules_snapshot_apply.sql
```

Notes
- Target Postgres 16
- Global DB keeps existing `public.rules*` from `0001_rules.sql`
- Two‑phase: ingest to Global → mover upserts to company DBs → sorting reads company DB only


### Confirmed decisions (affecting DDL and mover)
- Snapshot swap: truncate + bulk insert inside the company slice transaction
- Global snapshot store: persist snapshots in `control.rules_snapshots` with `snapshot_checksum`; track applied DDLs in `control.migrations`
- Company metadata: include `app.rules_meta` for local observability
- Error handling: rollback only the failing company slice; continue others

These choices drive the mover’s transaction shape (one transaction per company slice),
the presence of `app.rules_meta`, and ensure idempotent replays are safe.


