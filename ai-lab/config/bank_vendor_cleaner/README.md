# Bank Vendor Cleaner

## Status

Built, needs local testing.

## Purpose

Reads raw transaction descriptions from a single Google Sheet, writes:

- cleaned canonical labels to column C
- City/State values to column D

All writes are plain text only.

## Scope

- Single spreadsheet only
- Source tab: `transaction tab sheet`
- Destination tab: `CLEANED TRANSACTIONS-TAB SHEET`
- Source column: `C`
- Output columns: `C`, `D`

## Safety rules

- Never write formulas
- Never use ARRAYFORMULA / LET / regex formulas
- Never write below the last nonblank source row
- Never touch other spreadsheets by default
- Preserve exact row order

## Setup

1. Copy `config/bank_vendor_cleaner/settings.example.env`
2. Set `GOOGLE_APPLICATION_CREDENTIALS`
3. Confirm spreadsheet and tab names
4. Start with dry run only

## Run

```bash
python scripts/sheet_label_pipeline.py --dry-run
```

## Validation

Compare dry-run output against ChatGPT/agent output. Check that:

- labels in column C are canonical
- City/State in column D is aligned row-for-row
- no writes occur past the active data boundary
- no formulas are generated

## Todo

- [ ] Wire Google auth
- [ ] Add destination formula-detection abort
- [ ] Run all test vectors
- [ ] Enable approved live writes after dry-run validation
- [ ] Add scheduler only after stable local results

## Vendor lookup (v2)

Optional unknown-merchant research — **never writes C/D**.

- Worker: `scripts/vendor_lookup_worker.py`
- Runbook: `runbooks/bank_vendor_cleaner_vendor_lookup.md`
- Pipeline flag: `--vendor-lookup`

## Local model policy

- **Qwen operating prompt (primary):** `docs/bank_vendor_cleaner/QWEN_OPERATING_PROMPT.md`
- **Runtime policy (extended):** `docs/bank_vendor_cleaner/RUNTIME_POLICY.md`
- **Memory buckets:** `config/bank_vendor_cleaner/memory_buckets.yaml`
- **Command Center:** orchestrator injects `QWEN_OPERATING_PROMPT.md` via `brain/bank_vendor_cleaner/llm_context.py` for `bank_vendor_qa` and active-topic follow-ups
- **LM Studio stub:** `brain/prompts/bank_vendor_qwen_operating.txt` (pair with operating prompt when calling Qwen outside orchestrator)

Deterministic code owns writes. Qwen (or any local LLM) suggests aliases and interprets vendor lookup only; approved results promote into `memory_alias_map.yaml`.

## Notes

The Python script + YAML rules are the source of truth.

A local LLM may explain failures or suggest aliases, but must not decide production writes.
