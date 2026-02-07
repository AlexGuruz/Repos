# Incremental Posting Workflow

This document explains how the petty cash projection script now performs incremental
updates using a persistent state file. Use it alongside `docs/BASELINE_2025-11-09.md`
when preparing a new environment.

## Overview

- State lives at `.kylo/state.json` (override with `KYLO_STATE_PATH`).
- Each projected cell stores a SHA-256 signature of the contributing transaction
  UIDs and the total amount in cents.
- On every run, the script compares fresh signatures against the stored values and
  only posts cells whose signature changed.
- Optionally, verification mode reads existing Sheets values to detect manual edits
  even when signatures match.

## CLI

```powershell
# Baseline mode: write all cells and reseed state for a company
python bin/sort_and_post_from_jgdtruth.py --company NUGZ --baseline

# Incremental mode (default): skip unchanged cells
python bin/sort_and_post_from_jgdtruth.py --company NUGZ

# Force verification (read back skipped cells)
python bin/sort_and_post_from_jgdtruth.py --company NUGZ --verify
```

### Flags and Environment

| Flag / Env                | Purpose                                                                        |
|---------------------------|--------------------------------------------------------------------------------|
| `--baseline`              | Force a full write and clear existing signatures for the company               |
| `--verify` / `--no-verify`| Override read-back verification (default driven by `KYLO_VERIFY_POST`)        |
| `KYLO_POST_BASELINE`      | Treat the next run as baseline when set to `1/true`                            |
| `KYLO_VERIFY_POST`        | Enable verification mode when set to `1/true`                                  |
| `KYLO_STATE_PATH`         | Override the default `.kylo/state.json` location                               |

## State File Anatomy

```json
{
  "version": 1,
  "cell_signatures": {
    "NUGZ": {
      "CLEAN TRANSACTIONS|TOTAL|1/2/25": "296d0899..."
    }
  },
  "processed_txn_uids": {
    "NUGZ": ["9a8e...", "9d42...", "..."]
  }
}
```

- Keys inside `cell_signatures` use the pattern `"{tab}|{header}|{date}"` in uppercase.
- The signature hashes the sorted transaction UIDs plus the total amount (in cents).
- `processed_txn_uids` is informational; it records everything included in projections.

## Operational Checklist

1. Run `python bin/validate_config.py` to ensure the configuration is sane.
2. Execute a baseline run for each company (`--baseline`) after refreshing the rules.
3. Add the `.kylo/` directory to backups/restore scripts (already gitignored).
4. For day-to-day runs, call the CLI without flags; only changed cells are posted.
5. Enable verification (`KYLO_VERIFY_POST=1`) during audits to detect manual edits.

## Failure Modes & Recovery

- **Corrupted state file**: delete `.kylo/state.json` and re-run with `--baseline`.
- **Manual edits not overwritten**: re-run with `--verify` (or set `KYLO_VERIFY_POST=1`).
- **Process crash mid-run**: rerun; signatures keep it idempotent.
- **New company onboarding**: add config entries, then run `--baseline` for that company.


