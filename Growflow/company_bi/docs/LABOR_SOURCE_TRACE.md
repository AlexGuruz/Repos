# Labor Source Trace — Audit

**Goal:** Trace exactly how labor enters the system and how it flows into company_bi metrics.

---

## 1. Source file / report origin

- **Payroll is paid in cash** and recorded on the **employee petty cash sheet** (Google Sheets).
- **Petty cash CSV reports** are exported from that sheet (or equivalent tabs). Config references:
  - **Project-Kylo** `config/global.yaml`: companies use intake tab `"PETTY CASH"`; year workbooks point to the same intake workbook.
  - **Company_bi** `config/sources.yaml`: 2024 transactions use tab `["Petty Cash"]`; 2025/2026 use `["Transactions", "Bank"]` (which may receive cleaned data that originated from petty cash).

---

## 2. Ingestion path (CSV → database)

| Step | Location | Description |
|------|----------|-------------|
| 1 | Google Sheets | PETTY CASH tab holds rows: Initials, Date, Company, Source (description), Amount. |
| 2 | Download | `services/intake/csv_downloader.py` → `download_petty_cash_csv()` (Project-Kylo / Greg-Kylo). |
| 3 | Load to DB | **Project-Kylo**: `tools/ops_oneoffs/load_all_petty_cash_data.py`, `load_jgd_petty_cash.py`. Parse CSV → create batch in `control.ingest_batches` → insert into **`core.transactions_unified`**. |
| 4 | Optional mover | `services/mover/sql.py`: `core.transactions_unified` → company DB `app.transactions` (for rules/posting). |

- **Database:** PostgreSQL (`kylo_global`). DSN in Project-Kylo `config/global.yaml`: `database.global_dsn`.
- **Key table:** `core.transactions_unified` — columns used for labor: `posted_date`, `amount_cents`, `description`, `company_id`, `source_stream_id` (e.g. `petty_cash_csv`, `jgd_petty_cash_csv`).

---

## 3. Database tables / columns used for labor

- **Schema:** `db/ddl/0002_global_two_phase.sql` (Project-Kylo).
- **Table:** `core.transactions_unified`
  - `posted_date` (DATE) — for grouping by month.
  - `amount_cents` (BIGINT) — labor = sum of **expenses** (`amount_cents < 0`), so labor total = sum of `ABS(amount_cents)` for labor-matched rows.
  - `description` (TEXT) — matched against labor patterns (PAYROLL, WAGE, SQUARE TIPS, 941, etc.) same as `config/categories.yaml` labor section.
- **Labor identification:** No dedicated `category` column at ingest; labor is identified by **description ILIKE** patterns aligned with company_bi `categories.yaml` labor rules.

---

## 4. Transformation path into BI metrics (current vs intended)

### 4.1 Current (pre–labor-source correction)

- **Company_bi does not connect to the Kylo database.** It only reads from Google Sheets (Transactions, Bank, Petty Cash tabs per year).
- Labor in company_bi is **100% from transaction categorization**: normalized rows from Sheets → `apply_categorization()` → pattern match on description → `aggregate_by_category_month()` → `by_cat_month[(y,m)]["labor"]`.
- So **current labor = transaction inference from Sheets only**. DB-ingested petty-cash payroll is not used by company_bi.

### 4.2 Intended (post–labor-source correction)

- **Primary:** Labor from **DB-ingested petty-cash payroll**: query `core.transactions_unified` for rows where `amount_cents < 0` and `description` matches labor patterns; aggregate by `(year, month)` → labor total per month. Source tag: `db_petty_cash_payroll`, confidence: `confirmed`.
- **Fallback 2:** **Kylo PAYROLL tab** (per-year): Project-Kylo writes payroll transactions to a dedicated PAYROLL sheet; company_bi reads it (headers row 19, data from row 20, dates column A, amount column configurable). Source: `kylo_payroll_sheet`, confidence: `confirmed`. Config: `config/sources.yaml` → `payroll_sheet` (2025 / 2026 spreadsheet_id, tab `PAYROLL`).
- **Fallback 3:** Kylo budget sheet–derived labor totals (if/when available). Source: `kylo_budget`, confidence: `fallback`.
- **Fallback 4:** Transaction-based labor from Sheets categorization. Source: `transaction_inference`, confidence: `inferred`.
- **Double-count prevention:** Use a single source per month; do not add DB + payroll sheet + transaction labor for the same month.

---

## 5. Current gaps or distortions

| Gap | Description |
|-----|-------------|
| **DB not used** | Company_bi has no DB connection; it never reads `core.transactions_unified`. Labor is inferred only from Sheets, so any payroll present only in the DB (or better represented there) is not reflected. |
| **No source tagging** | Labor totals are not labeled by source (DB vs budget vs inference), so provenance is opaque. |
| **Possible under/overstatement** | If Sheets tabs are incomplete or lagged vs. DB, labor may be understated; if inference misclassifies non-labor as labor, overstated. |
| **No validation** | Pipeline does not check that DB labor was used when configured, or warn when inference is used despite DB being available. |

---

## 6. Summary

- **Source file:** Employee petty cash sheet → petty cash CSV (or equivalent export).
- **Ingestion path:** CSV → `load_all_petty_cash_data.py` / `load_jgd_petty_cash.py` → `core.transactions_unified` (kylo_global).
- **Tables/columns:** `core.transactions_unified.posted_date`, `amount_cents`, `description`; labor = sum of expense amounts where description matches labor patterns.
- **Transformation into BI:** Currently none from DB; company_bi uses only Sheets + categorization. After hardening: primary = DB labor by month; fallback = budget then transaction inference; labor_source and confidence in outputs.
- **Gaps:** DB labor unused; no source tagging; no validation of labor source priority.
