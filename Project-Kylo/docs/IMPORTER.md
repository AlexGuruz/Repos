## Importer — Pending → Active (Batch, Idempotent)

### Overview
This importer scans all tabs named `Pending Rules – <COMPANY>`, promotes rows with `Approved=TRUE` to the database as a new ruleset version, and projects a deduplicated `Active Rules – <COMPANY>` tab showing one row per unique `Source`. All Sheets writes are done via a single `spreadsheets.batchUpdate` call (no single‑cell writes).

Code: `scaffold/tools/importer.py`

### Column headers (current minimal)
- Pending: `Source, Target_Sheet, Target_Header, Approved`
- Active: `Source, Target_Sheet, Target_Header, Approved`

Setup helper applies these headers and protections: `scaffold/tools/sheets_batch.py`.

### Normalization
- Source: trimmed and lowercased for stable hashing; may include a short metadata note inserted by tooling (e.g., `[amt=$12.34, date=2025-08-15, id=txn:...]`).
- `Target_Sheet`, `Target_Header`: trimmed strings.

### Stable hash (idempotency)
`sha256(json.dumps({source, target_sheet, target_header}, sort_keys=True))`.
– Case/whitespace variations normalized by loader; `approved` is not part of the hash.

### Validation
- Blocking errors: NOT_APPROVED, SOURCE_EMPTY, TARGET_SHEET_EMPTY, TARGET_HEADER_EMPTY.

### Promotion logic
1) Batch read all Pending tabs using `values.batchGetByDataFilter`.
2) Normalize, validate. Skip blocking errors.
3) If `(company_id, source, row_hash)` already exists in DB, skip insert but queue a Processed_At writeback.
4) For new rows per company, open one DB transaction:
   - Create ruleset with `version = prior + 1`
   - Insert rules
   - Retire prior ruleset (if any)
   - Audit PROMOTE
5) Build a single batchUpdate:
   - Clear Active body and write unique‑source rows for each touched company
   - Write `Row_Hash` (A) and `Processed_At` (K) for processed Pending rows in contiguous blocks
 6) Cleanup: promoter automatically deletes Approved rows from per-company `rules_pending_<cid>` after a successful swap, but only after confirmation (count and checksum match). Sheets Pending rows can be manually cleared; loaders ignore banner rows.

### Active projection
- Minimal fields are projected; additional UI columns are optional and not part of `rule_json`.

### Processed_At timestamp
- America/Chicago (Oklahoma), DST‑aware.
- Format: `M/D/YY HH:MM:SS AM/PM`.

### Running tests
From repo root:
```powershell
python -m pytest -q scaffold
```

### Files added/changed
- Added: `scaffold/tools/importer.py`
- Added: `scaffold/tools/db_memory.py`
- Changed: `scaffold/tools/sheets_batch.py` (headers, protections)
- Added tests:
  - `scaffold/tests/test_importer_normalization.py`
  - `scaffold/tests/test_importer_validation.py`
  - `scaffold/tests/test_importer_idempotency.py`
  - `scaffold/tests/test_importer_integration.py`

### Notes
- All writes are performed in batch; no single‑cell updates are used.
- Amount ranges are not required for petty cash; exact numeric values are stored as `=value`.


