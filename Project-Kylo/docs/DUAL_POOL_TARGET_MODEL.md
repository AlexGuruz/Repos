# Dual-Pool Target Model

**Status:** Locked contract for sandbox (`KYLO_2026_SANDBOX`) and future live cutover.  
**Sandbox workbook:** `1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw`  
**Live 2026 (untouched):** `1oNVc-C03ePqLNE76sRUldzpLYsJWb2fo92rkM0_fqNE`

## Three layers (do not conflate)

| Layer | Job | Source of truth |
|-------|-----|-----------------|
| **Presentation** | Human-readable tabs (merge vs twin) | Workbook layout + rules Target Sheet/Header |
| **Pool attribution** | Every dollar is CASH, BANK, or TRANSFER for EOD | Rule `Pool` / intake tab → zone or helper totals |
| **Projection lifecycle** | Forecast in sheet until consumed by a real txn | Orphan scanner + near-date matcher |

**Fill color is UX only.** Available / Bank EOD / Cash EOD must **never** sum by color. Use zone subtotals or helper columns Kylo and formulas can read.

---

## Locked presentation map

| Target | Presentation | EOD feed |
|--------|--------------|----------|
| **EXPENSES** | Twin tabs `CASH EXPENSES` / `BANK EXPENSES` | Each tab daily B → matching EOD pot |
| **PAYROLL** | One `PAYROLL` tab; **cash people LEFT / bank people RIGHT** + source fill colors | Helper cols `Payroll Cash Net` + `Payroll Bank Net` at each zone end |
| **JGD** | One `JGD` tab with **Cash LEFT \| Bank RIGHT** column zones | Zone day totals → Cash EOD / Bank EOD |
| **NUGZ COG** | One `NUGZ COG` tab (cash pool only, left semantics) | All amounts → Cash EOD via tab B |
| **INCOME** | One `INCOME` tab with **Cash LEFT \| Bank RIGHT \| Transfers far-right** | Cash-group sum + Bank-group sum; transfers excluded from Available |
| **CC Payments** | One `CC Payments` tab (bank / right semantics) | Bank EOD only |
| **NON CANNABIS / ALLOCATED / CANNABIS DIST** | Single tabs (cash-primary) + source color | Pool helpers or journal attribution |

### Physical left / right column contract (sandbox)

Owner-facing rule: on every merged target tab, **CASH columns sit on the LEFT** and
**BANK columns sit on the RIGHT**, so daily projection amounts are SUM / SUMIF /
SUMRANGE-pullable from the correct side. Helper net columns sit at the **end of
each pool zone** (machine-readable for BALANCE G/H).

| Tab | Left (cash) | Right (bank) | Helpers (sandbox cols) |
|-----|-------------|--------------|------------------------|
| PAYROLL | person cols `C:S` | `GREG WREN` bank col `V` | Cash Net `T`, Bank Net `W` |
| JGD | `ATM LOAD` / `CLOVER` / `SERVICE FEE` (`C:E`) | `SWITCH` / `CLOVER (BANK)` / `SERVICE FEE (BANK)` (`H:J`) | Cash Net `F`, Bank Net `K` |
| INCOME | REG/sales cash headers (`C:L`) | SQUARE/VENMO/… (`O:V`) | Cash Net `M`, Bank Net `W`; transfers `Y:Z` + xfer nets `AA:AB` excluded from G/H |
| CASH EXPENSES | whole tab (day net `B`) | — | — |
| BANK EXPENSES | — | whole tab (day net `B`) | — |
| NUGZ COG / NON CANNABIS / ALLOCATED / CANNABIS DIST | whole tab (day net `B`) | — | — |
| CC Payments | — | whole tab (day net `B`) | — |

Migration / re-align: `python tools/debug/_align_left_cash_right_bank_sandbox.py`
(then rebuild BALANCE).

### Over-split tabs (hidden/frozen on sandbox)

`CASH PAYROLL`, `BANK PAYROLL`, `CASH JGD`, `BANK JGD`, `BANK NUGZ COG`, `CASH INCOME`, `BANK INCOME`, empty `BANK NON CANNABIS`, `BANK ALLOCATED`.

---

## BALANCE EOD formula contract

Opening seeds on `BALANCE`: Bank **$4,845.52**, Cash **$6,673.09**.

```
# d <= D0 (actual):    I/J from raw ledgers (SUMIFS)
# d >  D0 (projected):  I[d]=I[d-1]+H[d],  J[d]=J[d-1]+G[d]
AVAILABLE[d] = BankEOD[d] + CashEOD[d] + InTransit[d]
```

`L[d] = I[d] + J[d] + K[d]` always.

### Cash / Bank EOD: actual ledgers, then projected forward

The EOD is a **single continuous running line**. Let `D0` = the last actual day
(`max date in TRANSACTIONS/BANK`).

**Actual region (`d ≤ D0`)** — authoritative raw intake ledgers, **not** a sum of target tabs:

- **Cash EOD** `J = SUMIFS(TRANSACTIONS!D:D, TRANSACTIONS!A:A, "<="&date)` — the TRANSACTIONS
  tab IS the physical cash pool; its running balance is cash on hand. START OF YEAR
  ($6,673.09) seeds it.
- **Bank EOD** `I = $4,845.52 + SUMIFS(BANK!D:D, BANK!A:A, "<="&date)` — the BANK tab
  running balance.

This guarantees Cash EOD matches the TRANSACTIONS running balance per day exactly.

**Projection region (`d > D0`)** — the line continues using projected pool nets from
the target tabs so a planned shortfall is obvious:

- `J[d] = J[d-1] + G[d]`, `I[d] = I[d-1] + H[d]`
- `G` (Proj Cash Net) / `H` (Proj Bank Net) are live `SUMIF`s of the signed daily
  pool columns on the **left (cash) / right (bank)** layout
  (`CASH/BANK EXPENSES!B`, `PAYROLL!T/W`, `JGD!F/K`, `NUGZ COG!B`,
  `CANNABIS DIST!B`, `NON CANNABIS!B`, `ALLOCATED!B`, `INCOME!M/W`). INCOME transfer
  nets (`AA/AB`) are excluded so transfers never change Available.
- Ranges are spine-scoped (`$A$20:$A` / col `$20:$`) so month rollups on the 19th
  never collide with daily `xx/19` dates.

Map + formula builder + pure projector: `services/posting/projection_forecast.py`.
The target-tab reconstruction is the EOD source **only** past `D0`; for `d ≤ D0` the
raw ledgers remain authoritative.

### In Transit (K) — transfer matcher

Only **true $-for-$ transfers** bridge the timing gap (matched within **±3 days**, tol **$0.02**):

| Family | Cash leg | Bank leg | Effect |
|--------|----------|----------|--------|
| to_bank | `TO BANK` (TX) | `DEPOSIT` (BANK) | cash out today, bank in later → K holds the gap |
| from_bank | `FROM BANK` (TX) | `WITHDRAW` (BANK) | bank out today, cash in later → K holds the gap |

`ATM LOAD` ↔ `SWITCH` are **NOT** an in-transit pair: ATM LOAD is cash deployed into
the machine, SWITCH is ATM revenue settling to bank. Each stays on its own ledger.

`BALANCE!K` = running unmatched/lagged transfer float. Transfers never change Available.

**Drift alert:** a transfer leg that stays unreconciled longer than
`in_transit.drift_days` (default 7) is flagged on `BALANCE!K18` (with a note) and
emailed to the owner, naming the amount, age, and destination pool
(`TO BANK`→BANK, `WITHDRAW`→CASH). Detection `services/posting/in_transit_drift.py`;
email `services/notify/email_notifier.py` (sandbox uses `transport: gmail_api` — the
stashbox service account sends via the Gmail API as the delegated `notify.email.sender`;
SMTP is the fallback); repeat alerts deduped via `drift_alerts` in posting state.

### CashDayNet[d] / BankDayNet[d] (machine-readable)

| Source | Cash reference | Bank reference |
|--------|----------------|----------------|
| Expenses | `CASH EXPENSES!B{d}` | `BANK EXPENSES!B{d}` |
| Payroll | `PAYROLL!Payroll Cash Net` (`T`) | `PAYROLL!Payroll Bank Net` (`W`) |
| JGD | `JGD!JGD Cash Net` (`F`) | `JGD!JGD Bank Net` (`K`) |
| Income | `INCOME!Income Cash Net` (`M`) | `INCOME!Income Bank Net` (`W`) |
| NUGZ COG / cannabis / allocated / non-cannabis | tab `B{d}` | — |
| CC payments | — | `CC Payments!B{d}` |

**Attributed net includes:**

1. Posted / rule-matched amounts on day `d`.
2. Open projections still on day `d` (planned Available).
3. Minus projections consumed when a near-match posts within ±window (no double-count).

---

## Projection match contract

Defaults (locked): `window_days: 2`, `amount_tolerance: 0.02`, `clear_on_match: true`, `review_on_ambiguous: true`.

| Case | Kylo behavior |
|------|---------------|
| Manual projection; no matching intake yet | Leave value; counts in that day's EOD net |
| Actual posts same date + same header | Overwrite cell (poster); consume = `same_day_overwrite` |
| Actual posts ±2 days, same header, amount within $0.02, same sign, unambiguous | Write actual on actual date; **clear** projection cell on projected date; log to `PROJECTION CONSUMED` |
| Two candidates score equally | **Do not auto-clear**; write actual only; queue review |
| Partial amount (beyond tolerance) | Write actual; **leave residual** on projection date; flag review |
| Income year-grid (REG1/SQUARE forecasts) | Consume only when that header's intake posts |

### Match scoring

For projection `P` at `(sheet, header, date_p, amount_p)`:

1. Candidates `A`: same Target Sheet + Target Header, same sign, `|amount_A − amount_p| ≤ amount_tol`.
2. Date window: `date_A ∈ [date_p − W, date_p + W]`, W = 2.
3. Score: exact amount > nearest date > same month; ambiguous top-two → review queue.
4. Confident match: zero projection cell; append `PROJECTION CONSUMED` row; record in posting state `projection_consumptions[]`.

---

## Worked examples (from inspected cells)

### OEC bill (JGD EXPENSES legacy → BANK EXPENSES)

- Projection: **OEC −327.91** on **7/17** (manual ahead-of-date on legacy `JGD EXPENSES`).
- Actual: bank ACH posts **7/16** or **7/18** with same header.
- Matcher: if within ±2 days and $0.02, clears 7/17 projection, writes actual on post date → Available does not double-count.

### AT&T (bank expense)

- Projection: **AT&T −366.04** on **7/18**.
- Drift case: actual posts **7/17**; matcher clears 7/18 orphan after posting.

### ESTIMATED TAX / MJ TAX (NUGZ COG, cash pool)

- **ESTIMATED TAX −3000**, **MJ TAX −4584.23** on **7/20** on `NUGZ COG`.
- All amounts feed **Cash EOD** only (no bank twin).

### REG 1 income forecast (INCOME cash zone)

- Full-year **REG 1** daily prefills through Dec 2026.
- Forecast cells count in CashDayNet until a matching intake posts for that header/date window.
- Matcher does not treat all future REG1 cells as open A/P — only consumes on matching intake.

---

## Config shape

```yaml
posting:
  target_layout:
    PAYROLL: { mode: merged_color, eod: helper_totals, column_order: left_cash_right_bank }
    JGD: { mode: in_sheet_zones, zones: [CASH, BANK], column_order: left_cash_right_bank }
    EXPENSES: { mode: twin_tabs, cash_tab: CASH EXPENSES, bank_tab: BANK EXPENSES }
    INCOME: { mode: in_sheet_zones, zones: [CASH, BANK, TRANSFER], column_order: left_cash_right_bank }
    NUGZ_COG: { mode: single_pool, pool: CASH }
    CC_PAYMENTS: { mode: single_pool, pool: BANK }
  projection_match:
    enabled: true
    window_days: 2
    amount_tolerance: 0.02
    clear_on_match: true
    review_on_ambiguous: true
    include_tabs: [CASH EXPENSES, BANK EXPENSES, PAYROLL, NUGZ COG, INCOME, JGD, ...]
```

---

## Explicit non-goals (this pass)

- Changing live 2026 workbook.
- Using cell fill color as EOD input.
