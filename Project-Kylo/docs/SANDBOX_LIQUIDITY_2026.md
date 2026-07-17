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

## BALANCE running totals — continuous actual → projected EOD

The EOD line is **one continuous running balance**. Up to the last actual day
(`D0 = max date in TRANSACTIONS/BANK`) it is the raw account ledgers; past `D0`
it continues with projected pool nets pulled live from the target tabs, so a
projected shortfall visibly drives Available down (and negative).

| Col | Meaning | Actual region (`d ≤ D0`) | Projection region (`d > D0`) |
|-----|---------|--------------------------|------------------------------|
| **G** | Proj Cash Net | blank | live `SUMIF` of cash-pool target cells for the day |
| **H** | Proj Bank Net | blank | live `SUMIF` of bank-pool target cells for the day |
| **I** | Bank EOD | `$4,845.52 + SUMIFS(BANK!D:D, BANK!A:A, "<="&date)` | `=I(prev)+H` |
| **J** | Cash EOD | `SUMIFS(TRANSACTIONS!D:D, TRANSACTIONS!A:A, "<="&date)` (START OF YEAR $6,673.09 seeds it) | `=J(prev)+G` |
| **K** | In Transit | Running float of TRUE transfers mid-flight (`TO BANK↔DEPOSIT`, `FROM BANK↔WITHDRAW` only) | carries `K(D0)` |
| **L** | AVAILABLE | **`=I+J+K`** | **`=I+J+K`** |

Projection rows are **shaded** and the first projected row carries a note marking
where actuals end.

### Projected pool nets (cols G/H) — source columns

Signed daily values summed by pool (INCOME transfer nets AB/AC are excluded):

- **Cash (G):** `CASH EXPENSES!B`, `PAYROLL!V` (Payroll Cash Net), `JGD!K` (JGD Cash Net), `NUGZ COG!B`, `CANNABIS DIST!B`, `NON CANNABIS!B`, `ALLOCATED!B`, `INCOME!X` (Income Cash Net)
- **Bank (H):** `BANK EXPENSES!B`, `PAYROLL!W` (Payroll Bank Net), `JGD!L` (JGD Bank Net), `CC Payments!B`, `INCOME!Y` (Income Bank Net)

Map + formula builder live in `services/posting/projection_forecast.py`.

Day 1 check: **Available $12,036.96** with `L = I + J + K`.

**Cash EOD (J) ties to the TRANSACTIONS ledger to the penny for every actual day** — verified by
`tools/debug/_reconcile_cash_eod_vs_transactions.py` (max diff `0.0000`). The projection
region does not change actuals.

## In Transit drift alert

Transfer legs (`TO BANK`/`DEPOSIT`, `FROM BANK`/`WITHDRAW`) that stay unreconciled
longer than **`in_transit.drift_days` (default 7)** are flagged on `BALANCE!K18`
(with a note) and emailed to `alexstonedz@stonedprojects.com`, stating each
amount, days in transit, and which pool the funds should land in
(`TO BANK`→**BANK**, `WITHDRAW`→**CASH**).

- Detection: `services/posting/in_transit_drift.py`
- Email: `services/notify/email_notifier.py`. Sandbox uses `transport: gmail_api` — the
  **stashbox** service account (`stashbox@ai-dataframe.iam.gserviceaccount.com`, key
  `E:/secrets/gcp/sa.json`) sends via the Gmail API as the delegated mailbox
  `notify.email.sender`. Requires domain-wide delegation for the `gmail.send` scope.
  (SMTP transport via env `SMTP_HOST/PORT/USERNAME/PASSWORD/EMAIL_SENDER` is the fallback.)
- Dedupe: `drift_alerts` in posting state so the same drift is not re-emailed
- Config: `in_transit.drift_days`, `notify.email.*` in `KYLO_2026_SANDBOX.yaml`

**ATM LOAD / SWITCH are NOT netted through In Transit.** ATM LOAD is cash deployed
into the machine (real cash-out on TRANSACTIONS); SWITCH is ATM revenue settling
into the bank (real bank-in on BANK). They are not a $-for-$ transfer pair.

Rebuild script: `python tools/debug/_rebuild_balance_from_ledgers.py`

## Live intake mirror (every 120s)

Sandbox TRANSACTIONS + BANK stay current with the **live** 2026 workbook so EOD
can be validated day-to-day while you change sandbox layout/rules. **One-way
only** — never writes live; does not touch KYLO_2025 / KYLO_2026 watchers.

| Live tab | Sandbox tab | What is copied |
|----------|-------------|----------------|
| TRANSACTIONS | TRANSACTIONS | Full rows A:Z including Processed / Approved / NOTES / posting log text |
| BANK | BANK | Full rows A:Z including Processed / NOTES / posting log text |

When the live fingerprint changes the daemon copies those tabs, then rebuilds
BALANCE (advances D0, refreshes In Transit K). Unchanged polls are a cheap
read-only fingerprint (~seconds).

```powershell
cd E:\Repos\Project-Kylo
# Interactive (window + log tee)
.\scripts\active\start_sandbox_live_mirror.ps1

# Always-on Scheduled Task (boot/logon + 5m restart guard)
.\scripts\active\install_sandbox_live_mirror.ps1
Start-ScheduledTask -TaskName KyloSandboxLiveMirror

# One-shot verify
$env:PYTHONPATH = "E:\Repos\Project-Kylo"
$env:KYLO_INSTANCE_ID = "KYLO_2026_SANDBOX"
python scripts/sandbox_live_mirror_daemon.py --once --force
```

- Config: `sandbox_mirror.*` in `KYLO_2026_SANDBOX.yaml` (`interval_seconds: 120`)
- Module: `services/sandbox/intake_mirror.py`
- Daemon: `scripts/sandbox_live_mirror_daemon.py`
- Heartbeat: `.kylo/instances/KYLO_2026_SANDBOX/health/sandbox_mirror.json`
- Log: `.kylo/instances/KYLO_2026_SANDBOX/logs/sandbox_mirror.log`
- EOD check: `python tools/debug/_validate_sandbox_eod_vs_live.py`

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
