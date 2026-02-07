## Snapshot Tool Spec — Workbook Layout Discovery

Purpose: When a new target workbook URL is added to config, derive sheet aliases and propose a layout JSON with header_rows=19 and inferred columns.

Inputs
- company_id (UPPERCASE, from Column C)
- output_workbook URL (shared with the service account)

Behavior
- List sheets in the workbook; populate `sheet_aliases` from exact sheet titles (no guessing).
- For each relevant sheet (based on config or all sheets if unspecified):
  - Read header row 19; capture header cell texts.
  - Infer commonly used columns (e.g., Date, Amount) if present.
- Write a draft `data/layouts/<slug>-2025.json`:
```json
{
  "sheets": {
    "<Sheet Title>": { "header_rows": 19, "columns": { /* inferred, may be partial */ } }
  }
}
```
- Do not auto-commit; require operator approval to adopt.

Outputs
- Draft layout JSON
- Short report (stdout/log) of sheet titles and detected headers

CLI (planned)
```powershell
python -m tools.snapshot --company NUGZ --workbook "<url>" --out data/layouts/nugz-2025.json
```

Notes
- If a sheet lacks expected headers, leave `columns` empty and flag in the report.
- The tool is idempotent; re-running overwrites the draft layout.

