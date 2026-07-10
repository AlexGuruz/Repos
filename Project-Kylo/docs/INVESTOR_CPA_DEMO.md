# Investor / CPA Demo Outline — Project Kylo

**Updated:** 2026-07-10  
**Mode:** Read-only / dry-run — **no live posting during demo**

---

## Purpose

Demonstrate how Kylo automates petty-cash classification from dispensary intake sheets into JGDTruth financial workbooks, with forensic controls suitable for CPA review.

---

## Audience messaging

| Audience | Focus |
|----------|-------|
| Investor | Automation ROI, multi-company scale, audit trail |
| CPA | Traceability, reconciliation, manual-edit detection, idempotency |

---

## Pre-demo checklist

- [ ] Confirm `posting.sheets.apply: false` and `runtime.mode: audit`
- [ ] Set `KYLO_READ_ONLY=1` in demo shell
- [ ] Do **not** run production enablement scripts
- [ ] Have 2026 intake workbook open (read-only share)
- [ ] Have JGDTruth rules workbook open (read-only)

---

## Demo script (30–45 minutes)

### 1. Problem statement (5 min)

- Manual petty-cash allocation across NUGZ, EMPIRE, PUFFIN, JGD
- Year split: 2025 vs 2026 workbooks
- Risk: partial totals, duplicate posts, undetected sheet edits

### 2. Architecture walkthrough (5 min)

- Two-workbook model (rules vs transactions) — `docs/sheets_contract.md`
- Year instances: KYLO_2025, KYLO_2026
- Show config layering diagram — `docs/ARCHITECTURE_AND_DATA_FLOW.md`

### 3. Intake → rules → targets (10 min)

- Open 2026 TRANSACTIONS intake tab
- Show rule example in JGDTruth (source → target_sheet + target_header)
- Explain **cell signature** incremental posting — `docs/INCREMENTAL_POSTING.md`

### 4. Bug fix narrative (5 min) — **Implemented**

- **Before:** Target cells summed only unposted rows → wrong totals
- **After:** All matched rows sum; only unposted rows get Column F mark
- Show passing tests:

```powershell
python -m pytest scaffold/tests/posting/test_incremental_posting.py -v --noconftest
```

### 5. Forensic audit (10 min) — **Implemented**

- `runtime.mode: audit` — snapshots, row diffs, highlights
- Show `data/audit/kylo_2026_transactions_backlog.yaml`
- Explain Column G audit notes vs Column F posted flag
- **CPA point:** `mark_posted: false` during investigation — Kylo won't flip posted flags until approved

### 6. Dry-run evidence (5 min)

- Show config gate output (no writes):

```
[POSTING] dry_run=True (posting.sheets.apply=False, ...)
[POSTING] Writes DISABLED due to: config:posting.sheets.apply=false
```

- Reference variance tooling (offline): `tools/debug/_compare_2025_intake_vs_posted.py` (read-only)

### 7. Production path (5 min) — **Planned / gated**

- Outline `docs/OPERATIONS_RUNBOOK.md` production enablement
- Emphasize: power-1 deployment, CPA sign-off, soak period

---

## What to label explicitly

| Capability | Status |
|------------|--------|
| JGDTruth incremental posting | **Implemented** (fix in tree) |
| Forensic audit mode | **Implemented** |
| Multi-year watchers | **Implemented** |
| Kafka / n8n scale-out | **Planned** |
| Production posting (2026) | **Frozen** — pending validation |
| worker-node Kylo | **Deprecated** |

---

## FAQ (CPA)

**Q: Can Kylo overwrite accountant manual edits?**  
A: Incremental signatures + optional verify mode detect drift; audit mode logs all intake changes. Repair path rewrites only verified-bad cells when posting enabled.

**Q: How do we know a row was posted?**  
A: Column F (when `mark_posted: true`), Column G notes, posting_state signatures, watcher logs.

**Q: What failed in 2026?**  
A: Documented in audit backlog manifest; partial-total bug contributed; full reconciliation in progress.

---

## Materials to share (read-only)

- `docs/ORCHESTRATOR_REPORT_2026-07-10.md`
- `docs/INCREMENTAL_POSTING.md`
- `docs/WORKSHEET_QUICK_REFERENCE.md`
- Test output (incremental posting 3/3 pass)

**Do not share:** service account JSON, DSN passwords, `.env` contents.
