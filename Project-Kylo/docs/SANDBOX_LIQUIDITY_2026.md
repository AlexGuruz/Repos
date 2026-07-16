# 2026 Liquidity Sandbox

**Status:** Dual-pool **collapsed** target model live on sandbox (2026-07-15). Live 2026 workbook still untouched. 2025 untouched.

## Open this

https://docs.google.com/spreadsheets/d/1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw/edit

Shared as **writer** with `alexstonedz@stonedprojects.com`.

Live (do not edit for this project): `1oNVc-C03ePqLNE76sRUldzpLYsJWb2fo92rkM0_fqNE`

Full contract: [`DUAL_POOL_TARGET_MODEL.md`](DUAL_POOL_TARGET_MODEL.md)

## Target layout (collapsed)

| Keep | Merged / single |
|------|-----------------|
| **CASH EXPENSES** + **BANK EXPENSES** (twins) | **PAYROLL** (one tab + source color + helper nets) |
| | **JGD** (Cash \| Bank zones + helper nets) |
| | **INCOME** (Cash \| Bank \| Transfer zones + helper nets) |
| | **NUGZ COG** (cash only), **CC Payments**, **NON CANNABIS**, **ALLOCATED**, **CANNABIS DIST** |

### Hidden over-split twins

`CASH PAYROLL`, `BANK PAYROLL`, `CASH JGD`, `BANK JGD`, `BANK NUGZ COG`, `CASH INCOME`, `BANK INCOME`, `BANK NON CANNABIS`, `BANK ALLOCATED`.

Rules retarget to merged tabs. Legacy tabs (`JGD EXPENSES`, etc.) remain for reference only.

### EOD helper columns (machine-readable)

| Tab | Helpers |
|-----|---------|
| PAYROLL | `Payroll Cash Net`, `Payroll Bank Net` |
| JGD | `JGD Cash Net`, `JGD Bank Net` |
| INCOME | `Income Cash Net`, `Income Bank Net` |

Fill color is UX only — EOD never sums by color.

## BALANCE running totals

**Cash and Bank EOD are the actual account ledgers, not reconstructions.**

| Col | Meaning | Formula |
|-----|---------|---------|
| **I** | Bank EOD | `$4,845.52 + SUMIFS(BANK!D:D, BANK!A:A, "<="&date)` — the BANK tab running balance |
| **J** | Cash EOD | `SUMIFS(TRANSACTIONS!D:D, TRANSACTIONS!A:A, "<="&date)` — the TRANSACTIONS running balance (START OF YEAR $6,673.09 seeds it) |
| **K** | In Transit | Running float of TRUE transfers mid-flight (`TO BANK↔DEPOSIT`, `FROM BANK↔WITHDRAW` only) |
| **L** | AVAILABLE | **`=I+J+K`** |

Day 1 check: **Available $12,036.96** with `L = I + J + K`.

**Cash EOD (J) ties to the TRANSACTIONS ledger to the penny every day** — verified by
`tools/debug/_reconcile_cash_eod_vs_transactions.py` (max diff `0.0000`).

**ATM LOAD / SWITCH are NOT netted through In Transit.** ATM LOAD is cash deployed
into the machine (real cash-out on TRANSACTIONS); SWITCH is ATM revenue settling
into the bank (real bank-in on BANK). They are not a $-for-$ transfer pair.

Rebuild script: `python tools/debug/_rebuild_balance_from_ledgers.py`

`START OF YEAR` rule is **disabled** for posting; the $6,673.09 START OF YEAR row on
TRANSACTIONS is the cash opening that seeds the `J` ledger.

## Projection consumption

Kylo clears ahead-of-date manual literals when a matching actual posts within **±2 days**, same header, same sign, amount within **$0.02** (unambiguous only).

- Log tab: **PROJECTION CONSUMED**
- Config: `posting.projection_match` in `KYLO_2026_SANDBOX.yaml`
- Module: `services/posting/projection_matcher.py`

## How to re-post sandbox

```powershell
cd E:\Repos\Project-Kylo
$env:PYTHONPATH = "E:\Repos\Project-Kylo"
$env:KYLO_INSTANCE_ID = "KYLO_2026_SANDBOX"
python bin/sort_and_post_from_jgdtruth.py --company JGD --baseline --reprocess-posted --rules-changed
python bin/sort_and_post_from_jgdtruth.py --company NUGZ --baseline --reprocess-posted --rules-changed
```

## Collapse + wire (one-time maintenance)

```powershell
python tools/debug/_collapse_dual_pool_sandbox.py
```

## Still open

1. **PAYROLL helper attribution** — person columns may still show SUM formulas until post+rebuild; Bank Net from intake rebuild  
2. **CANNABIS DIST vs NUGZ COG** — `BALANCE` Cash EOD **excludes** `CANNABIS DIST` to avoid double-count  
3. Only after sandbox sign-off: retarget live 2026  
