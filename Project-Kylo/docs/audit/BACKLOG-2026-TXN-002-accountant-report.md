# Kylo Forensic Audit Report — Case BACKLOG-2026-TXN-002

**Prepared for:** Accountant / CPA review  
**Company scope:** JGD (2026 intake)  
**Detection date:** July 10, 2026  
**Flags applied to live sheet:** July 10, 2026 at 17:47 UTC  

---

## 1. Executive Summary

Kylo's automated forensic audit system (**KYLO_FORENSIC_AUDIT_SYSTEM**, instance **KYLO_2026**) identified **post-hoc edits** to the 2026 intake **TRANSACTIONS** log. The findings fall into three categories:

| Category | Count | Nature of issue |
|----------|------:|-----------------|
| **Inserted rows** | 2 | FROM BANK / PAYROLL pairs added after the original log was posted |
| **Changed amounts** | 2 | FROM BANK amounts altered vs. prior PETTY CASH / intake records |
| **False payroll transactions** | 4 (2 pairs) | Fabricated FROM BANK + PAYROLL pairs that net to zero, inflating apparent payroll without legitimate underlying payments |

**Case ID:** `BACKLOG-2026-TXN-002`  
**Scope:** Eight rows on the intake **TRANSACTIONS** tab only (spreadsheet `1oNVc-C03ePqLNE76sRUldzpLYsJWb2fo92rkM0_fqNE`).  
**Forensic lower bound:** None of the eight flagged rows appear in a January 5, 2026 local snapshot (24 rows through 1/5/26), so all suspect edits occurred **on or after January 6, 2026**.  
**Suspected actor (estimate):** **JJN** — initials recorded in column B of the PETTY CASH raw log on matching rows. This indicates who logged the raw entry, not necessarily who edited the intake sheet.

---

## 2. How to Read the Flags on the TRANSACTIONS Sheet

Each flagged row has two visible indicators:

### Row highlights (background tint)

| Tint | Meaning |
|------|---------|
| **Light pink** | Inserted row |
| **Amber / light orange** | Changed amount |
| **Stronger red / pink** | False payroll transaction (inserted + edited) |

Highlights are applied across columns A–G on the affected row.

### Column G note format

Every flagged row carries a structured note prefixed with:

`KYLO-AUDIT-SYSTEM | BACKLOG-2026-TXN-002`

The note fields are pipe-separated (`|`) and read left to right:

| Field | Example |
|-------|---------|
| System + case ID | `KYLO-AUDIT-SYSTEM \| BACKLOG-2026-TXN-002` |
| Finding type | `INSERTED ROW`, `CHANGED AMOUNT`, or `FALSE TRANSACTION — INSERTED ROW + EDITED AMOUNT` |
| Transaction summary | Date, company, description, amount |
| Kylo posting destination | e.g. `Posted 2000.00 -> INCOME/FROM BANK 3/30/26` |
| Paired row (if applicable) | e.g. `paired row 632` |
| Plain-English explanation | Why the row was flagged |
| Estimated edit window | e.g. `est. edit window: 2026-03-27 to 2026-04-03` |
| Suspected actor | `actor: JJN (PETTY CASH initials)` |
| Confidence | `confidence: medium` |
| Detection timestamp | `detected 2026-07-10T17:35:00Z` |
| Attribution | `automated forensic audit \| NOT manual user entry` |

**Important:** Column G still contains the original Kylo posting note (e.g. `Posted … -> TAB/HEADER date`). The audit note documents the forensic finding; it does not replace the posting record.

---

## 3. All Eight Flagged Transactions

| Row | Date | Description | Amount | Category | Paired Row | Kylo Posting Destination |
|-----|------|-------------|--------|----------|------------|--------------------------|
| **631** | 3/30/26 | FROM BANK | $2,000.00 | Inserted row | 632 | Posted 2000.00 → INCOME/FROM BANK 3/30/26 |
| **632** | 4/3/26 | PAYROLL 31971 | ($2,000.00) | Inserted row | 631 | Posted -2000.00 → PAYROLL/JENIFER WREN 4/3/26 |
| **639** | 3/31/26 | FROM BANK | $2,700.00 | Changed amount | — | Posted 2700.00 → INCOME/FROM BANK 3/31/26 |
| **684** | 4/6/26 | FROM BANK | $3,000.00 | False payroll | 685 | Posted 3000.00 → INCOME/FROM BANK 4/6/26 |
| **685** | 4/6/26 | PAYROLL 31971 | ($3,000.00) | False payroll | 684 | Posted -3000.00 → PAYROLL/JENIFER WREN 4/6/26 |
| **686** | 4/6/26 | FROM BANK | $33,305.00 | Changed amount | — | Posted 33305.00 → INCOME/FROM BANK 4/6/26 |
| **790** | 4/20/26 | FROM BANK | $2,000.00 | False payroll | 791 | Posted 2000.00 → INCOME/FROM BANK 4/20/26 |
| **791** | 4/20/26 | PAYROLL 24950 | ($2,000.00) | False payroll | 790 | Posted -2000.00 → PAYROLL/GREG WREN 4/20/26 |

### Grouping summary

| Group ID | Rows | Issue |
|----------|------|-------|
| INSERT-2026-0330-PAYROLL-31971 | 631, 632 | Inserted FROM BANK / PAYROLL pair |
| CHANGED-2026-0331-FROM-BANK | 639 | FROM BANK amount altered |
| FALSE-PAYROLL-2026-0406 | 684, 685 | Fabricated zero-net payroll pair |
| CHANGED-2026-0406-FROM-BANK-33305 | 686 | FROM BANK amount altered |
| FALSE-PAYROLL-2026-0420 | 790, 791 | Fabricated zero-net payroll pair |

**Net financial impact of false payroll pairs:** $0 (pairs offset). The concern is **misrepresentation of payroll activity**, not a net cash imbalance on those pairs.

---

## 4. Estimated Edit Sessions (Estimates — Not Proof)

> **Disclaimer:** These timing windows are forensic **estimates** derived from PETTY CASH initials, the January 5 snapshot absence, and transaction-date clustering. They are **not proof** of when edits occurred. Confidence is **medium** for all three sessions.

### Session 1 — Late March insert + amount change

| Attribute | Detail |
|-----------|--------|
| **Estimated window** | March 27, 2026 – April 3, 2026 |
| **Suspected actor** | JJN |
| **Confidence** | Medium |
| **Intake rows affected** | 631, 632, 639 |
| **PETTY CASH JJN rows** | 632, 633, 634, 635 |

**Evidence:**

- JJN entered a block of FROM BANK / PAYROLL pairs in PETTY CASH between 3/27 and 4/3
- Intake rows 631/632 (inserted 3/30 + 4/3 pair) and row 639 (3/31 amount change) align with this batch
- Adjacent JJN raw rows 632/633 ($1,000 pair) show the same batch-entry pattern but are **not** flagged
- Row 632 shows **date inversion**: transaction date 4/3 but inserted adjacent to 3/30 row 631 in the same batch

---

### Session 2 — April 6 false payroll + amount change

| Attribute | Detail |
|-----------|--------|
| **Estimated window** | April 3, 2026 – April 10, 2026 |
| **Suspected actor** | JJN |
| **Confidence** | Medium |
| **Intake rows affected** | 684, 685, 686 |
| **PETTY CASH JJN rows** | 687, 688, 689, 690, 691, 692, 693 |

**Evidence:**

- Seven JJN entries on 4/6 in PETTY CASH, including the $3,000 false payroll pair (raw 687/688) and $33,305 FROM BANK (raw 689)
- Intake rows 684–686 match this cluster
- Other 4/6 JJN entries (sales taxes, legitimate payroll) exist in PETTY CASH but were **not** flagged

---

### Session 3 — April 20 false payroll pair

| Attribute | Detail |
|-----------|--------|
| **Estimated window** | April 17, 2026 – April 27, 2026 |
| **Suspected actor** | JJN |
| **Confidence** | Medium |
| **Intake rows affected** | 790, 791 |
| **PETTY CASH JJN rows** | 793, 794 |

**Evidence:**

- JJN initials on PETTY CASH 4/20 FROM BANK $2,000 + PAYROLL 24950 ($2,000)
- Intake rows 790/791 form a zero-net fabricated payroll pair

---

## 5. Limitations and What Would Tighten the Timeline

| Limitation | Impact |
|------------|--------|
| **Google Sheets version history not consulted** | Cannot pin exact edit timestamps or editor identity on the intake sheet |
| **PETTY CASH dates are transaction dates, not entry timestamps** | JJN batch clustering provides windows, not precise times |
| **JJN initials indicate who logged the raw entry** | Does not prove who edited the intake TRANSACTIONS tab |
| **Kylo watcher.log records batch posting counts only** | No per-row edit timestamps in system logs |
| **Confidence capped at medium** | No corroborating per-row timestamps available |

**What would tighten the timeline:** Google Sheets **Version History** on the intake **TRANSACTIONS** tab would provide exact edit dates, times, and (where available) editor accounts for each of the eight rows.

---

## 6. What Was NOT Flagged

### Prior incorrect flags removed (22 rows)

Before case **BACKLOG-2026-TXN-002** was applied, Kylo cleared **22 incorrect flags** from the superseded case **BACKLOG-2026-TXN-001**:

- Highlights removed on 22 rows
- Original Kylo posting notes restored on those 22 rows

Those 22 rows are **not** part of the current audit and should **not** be treated as findings under BACKLOG-2026-TXN-002.

### Other JJN PETTY CASH activity not flagged

The PETTY CASH raw log contains **28 total JJN-initialled rows**. Only the eight intake rows above were flagged. Examples of **legitimate JJN activity not flagged** include:

- 1/23/26 JGD ATM LOAD ($500)
- 3/13/26 JGD FROM BANK / PAYROLL 31971 pair ($3,013.75)
- 3/25/26 NUGZ vendor orders (six rows)
- 3/27/26 JGD FROM BANK $1,000 + 4/3/26 PAYROLL 31971 ($1,000) — same batch pattern as flagged rows, but not flagged
- 4/3/26 JGD MONEY DROP / ATM LOAD
- 4/6/26 JGD sales taxes and legitimate payroll (rows 690–693)
- 6/1/26, 6/5/26, 6/19/26, 6/30/26 JGD entries

### Other anomalies outside this case

Broader backlog analysis identified other data-quality items (e.g., row 1119 invalid date, NUGZ amount revision on 1/5/26) that are **separate** from this forensic case and were **not** flagged under BACKLOG-2026-TXN-002.

---

## 7. Reference Artifacts

| Artifact | Path |
|----------|------|
| Audit manifest (8 flagged transactions) | `data/audit/kylo_2026_transactions_backlog.yaml` |
| Estimated edit timeline | `data/audit/kylo_2026_false_edit_timeline.yaml` |
| Applied-state record (notes + highlights) | `.kylo/instances/KYLO_2026/state/audit_backlog_applied.json` |
| Pre-apply snapshot | `.kylo/instances/KYLO_2026/snapshots/BACKLOG-BACKLOG-2026-TXN-002-2026-07-10T17-47-26` |
| Restore posted-notes CSV | `tools/debug/_2026_txn_posted_backlog.csv` |
| Jan 5 local CSV snapshot | `.kylo/instances/JGD_2026/tmp/TRANSACTIONS_2026.csv` |
| Full backlog debug export | `tools/debug/_2026_txn_backlog.csv` |
| PETTY CASH raw log | Spreadsheet `1GizTKLceyoVVOVAIDrODebYbCK4hRhD5Q9jZ-s0qgIs`, tab **PETTY CASH** |
| Intake TRANSACTIONS (live flags) | Spreadsheet `1oNVc-C03ePqLNE76sRUldzpLYsJWb2fo92rkM0_fqNE`, tab **TRANSACTIONS** |

---

*This report was generated from Kylo forensic audit artifacts. Edit-session timing and actor attribution are estimates based on available evidence, not legal proof of alteration. For CPA workpapers, pair this report with Google Sheets version history and bank/payroll source documents for the flagged dates.*
