## Kylo Documentation Index (Maintenance)

Authoritative source of truth (archived planning):
- See `../archive/docs/planning/PDR.md` for product/design requirements, decisions, schemas, mover contract, eventing, Sheets policy, tests, and the rolling checklist.

Supporting documents:
- `docs/IMPORTER.md`: Batch-only importer spec and tests overview.
- `docs/DRY_RUN_CHECKLIST.md`: Minimal flow to validate idempotency and approvals.
- `../archive/docs/planning/REPLICATOR_AND_MIGRATIONS_PLAN.md`: Replicator/migrations outline (archived).
- `docs/SNAPSHOT_TOOL_SPEC.md`: Workbook layout discovery tool spec.
- `docs/WORKSHEET_ARCHITECTURE.md`: Comprehensive guide to worksheet architecture, tab naming conventions, and operational protocols.
- `docs/sheets_contract.md`: Sheets contract and posting protocols.
- `docs/WORKSHEET_QUICK_REFERENCE.md`: Quick reference guide for worksheet protocols and troubleshooting.
- n8n orchestration: See section "12) n8n — Batch Mover Orchestration" in `../archive/docs/planning/PDR.md`.
 - n8n master workflow JSON: `services/n8n/workflows/master_kylo.json` (import into n8n)

Notable updates (2025-08):
- Added `KYLO_*` env namespace in `scaffold/example.env`.
- Optional observability table `control.mover_runs` and metrics write in mover.
- Mover now supports env-configurable COPY threshold and transient retry.
- Sheets poster stub at `services/sheets/poster.py` with a unit test.
- CI workflow at `.github/workflows/ci.yml` runs unit + integration tests.

Critical fix (2025-01-XX):
- **Worksheet Architecture Fix:** Resolved critical issue where rules management operations were incorrectly targeting company transaction workbooks instead of the dedicated Rules Management Workbook.
- **Strict Separation Enforced:** All services now respect the two-workbook architecture with no cross-contamination.
- **Tab Naming Standardized:** Updated all services to use current naming convention (`"{CID} Pending"`, `"{CID} Active"`).
- **Legacy Cleanup:** Rule management tabs in company transaction workbooks should be deleted.
 - Rules: added per-row `rule_hash` (sha256 of rule_json) and optional `last_checksum` on `control.company_rules_version`.
 - Tooling:
  - `python services/rules_loader/loader.py --xlsx Rules.xlsx --dsn-map-file config/dsn_map.json` loads Pending into per-company `rules_pending_<cid>` (minimal schema: source, target_sheet, target_header, approved).
  - `python services/rules_loader/sheets_loader.py --spreadsheet <ID_OR_URL> --service-account secrets/service_account.json --dsn-map-file config/dsn_map.json` loads Pending from Sheets to DB.
  - `python scaffold/tools/promote_from_pending.py --dsn-map-file config/dsn_map.json` promotes Approved pending into `app.rules_active` snapshot.
     - Prune: After a successful swap (count+checksum confirmed), Approved rows are automatically deleted from per-company `rules_pending_<cid>`. Sheets Pending rows can be cleared manually (banner rows are ignored by loaders).
  - `python scaffold/tools/add_pending_note.py --company <CID> --source "..." --amount "$12.34" --date "YYYY-MM-DD" --id txn:... --dsn-map-file config/dsn_map.json [--spreadsheet <ID_OR_URL>]` adds a pending rule with a metadata note in Source.
- Intake tabs currently include only `TRANSACTIONS` and `BANK`; the historical `CREDIT CARDS` sheet has been retired from all workbooks, so `intake.extra_tabs` remains empty.
 - Global: added `control.rules_snapshots(company_id, version, snapshot JSONB, snapshot_checksum)` and `control.migrations` ledger; idempotent DDL with IF NOT EXISTS.
 - Company: added `app.apply_rules_snapshot(jsonb)` function and `app.rules_active_checksum` view; snapshot swap is truncate+insert.

Notes:
- Any future docs should align with `docs/PDR.md`. If overlap occurs, prefer updating the PDR and linking from here rather than creating parallel documents.


