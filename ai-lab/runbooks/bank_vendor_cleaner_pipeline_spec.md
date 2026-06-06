# Bank Vendor Cleaner — pipeline spec

Deterministic Google Sheets pipeline: read source column C → write destination columns C (label) and D (City/State) as **plain values only**.

**Script:** `scripts/sheet_label_pipeline.py`  
**Registry tool:** `bank_vendor_cleaner_pipeline`  
**Config:** `config/bank_vendor_cleaner/`  
**Reports:** `reports/bank_vendor_cleaner_run_report.json`  
**Agent README:** `config/bank_vendor_cleaner/README.md`

---

## Config

Copy `config/bank_vendor_cleaner/settings.example.env` and set paths/secrets.

| Variable | Default | Purpose |
|----------|---------|---------|
| `SPREADSHEET_ID` | manifest | Target spreadsheet |
| `SOURCE_SHEET_NAME` | transaction tab sheet | Read column C |
| `DEST_SHEET_NAME` | CLEANED TRANSACTIONS-TAB SHEET | Write C/D |
| `START_ROW` | 2 | First data row |
| `DRY_RUN` | true | Preview only |
| `APPROVAL_REQUIRED` | true | Live writes need `--approved` |
| `GOOGLE_APPLICATION_CREDENTIALS` | — | Service account JSON |
| `REPORT_DIR` | reports | Run report output |

---

## Algorithm

1. Load config + manifest; assert spreadsheet/sheet scope.
2. Open spreadsheet; read source column C from `START_ROW`.
3. Boundary = last nonblank row in source C.
4. For each row (top to bottom):
   - alias lookup (`memory_alias_map.yaml`)
   - ordered canonical rules (`cleaning_rules.yaml` + engine)
   - deterministic city/state extraction
5. Build plain-text write payloads for destination C and D.
6. Abort if payloads look like formulas (`=` prefix).
7. If `DRY_RUN=true`: print preview + write report JSON; stop.
8. If live: require `--approved`; optionally abort if destination has formulas (unless `REPLACE_FORMULAS=true`).
9. Write C and D as `RAW` values; emit report.

## What must NOT use an LLM

- Read boundary, alias lookup, rule matching, city/state regex, row order, write range, formula guard, dry-run, reporting.

## What MAY use an LLM (optional)

- Explaining unknown merchants, suggesting aliases for human review — never direct writes.

## Idempotency & safety

- Wrong spreadsheet/sheet → abort.
- Live writes: `DRY_RUN=false` + `--approved`.
- Never write below last nonblank source row.
- Never write formulas.

---

## Commands

```powershell
pip install -r requirements-bank-vendor-cleaner.txt

# Dry-run (default)
python scripts/sheet_label_pipeline.py --dry-run

# Live write (after validation)
python scripts/sheet_label_pipeline.py --no-dry-run --approved
```

## Chat triggers

- clean sheet labels
- run label pipeline
- run bank vendor cleaner
- backfill cleaned transactions

## Tests

```powershell
pytest tests/test_bank_vendor_cleaner.py -q
```

32 fixture vectors; no Google API required.

## Schedule (after validation)

- Initial: daily cron with `DRY_RUN=true`
- Later: approved live writes on a fixed schedule
