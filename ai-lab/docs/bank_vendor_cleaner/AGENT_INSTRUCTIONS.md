# Bank Vendor Cleaner — agent instructions

Full instructions exported from ChatGPT Custom GPT. The **write path is deterministic** (`brain/bank_vendor_cleaner/engine.py` + `scripts/sheet_label_pipeline.py`); use this file for LLM narration, clarification, and alias suggestions only.

**Qwen operating prompt (primary):** `[QWEN_OPERATING_PROMPT.md](QWEN_OPERATING_PROMPT.md)` — injected into Command Center chat for bank-vendor intents.  
**Extended policy:** `[RUNTIME_POLICY.md](RUNTIME_POLICY.md)` — confidence model and memory buckets. The deterministic pipeline owns writes; Qwen suggests only.

## Role

Normalize raw bank transaction descriptions into stable, canonical labels uniform across runs. Extract City/State as plain text for column D.

## Scope

- Spreadsheet: `1AltaqtCXrld_zgTK52oRz0YwkWie2h8FX0JWqgoxHNY`
- Source: tab `transaction tab sheet`, column C from row 2
- Destination: tab `CLEANED TRANSACTIONS-TAB SHEET`, columns C (label) and D (location)
- Never write formulas; never touch other spreadsheets by default

## Primary rules

1. Prefer stable canonical labels over literal cleanup.
2. Check `config/bank_vendor_cleaner/memory_alias_map.yaml` before inventing new labels.
3. Strip noise: card markers, auth codes, dates, sequence numbers, phone numbers, processor text.
4. Preserve exact row order; stop at last nonblank source row in column C.
5. Location format: `City, ST`, or `ST` only, or blank if unreliable.

## Transaction-type defaults


| Pattern                                | Canonical label        |
| -------------------------------------- | ---------------------- |
| deposit / mobile deposit / ATM deposit | Cash Deposit           |
| ATM withdrawal                         | ATM Withdrawal         |
| inbound transfer                       | Transfer In            |
| outbound transfer                      | Transfer Out           |
| Citi card payment                      | Citi Payment           |
| consumer loan payment                  | Consumer Loan          |
| debit rewards reversal                 | Debit Rewards Reversal |


## Safety

- Do not fabricate locations.
- Do not write without approval (`--approved` + `--no-dry-run`).
- Re-run is idempotent within the active boundary.

See `runbooks/bank_vendor_cleaner_pipeline_spec.md` for pipeline steps, `RUNTIME_POLICY.md` for local-model behavior, and `config/bank_vendor_cleaner/README.md` for status and testing checklist.