# Session restore — canonical zoned layout

**Machine:** Acheron (`E:\Repos`)  
**Path migration:** July 2026  
**Reviewed:** 2026-08-05

Open this folder in Cursor: **`E:\Repos`**  
Or multi-root workspace: **`E:\Repos\Repos.code-workspace`**

> **Important:** Product folders moved into zones. Read [`AGENTS.md`](../AGENTS.md) and [`docs/REPO_PATH_MIGRATION.md`](../docs/REPO_PATH_MIGRATION.md). Commands below use canonical paths; old flat paths in historical notes are not valid.

---

## What you were working on (3 tracks)

### 1. Repo cleanup / three-machine sync — mostly done

| Doc | Purpose |
|-----|---------|
| [docs/PHASES_2-6_RESULTS.md](../docs/PHASES_2-6_RESULTS.md) | Phase 1–6 completion (sync + GitHub push) |
| [docs/THREE_MACHINE_REPO_ALIGNMENT.md](../docs/THREE_MACHINE_REPO_ALIGNMENT.md) | Acheron / power-1 / worker-node alignment audit |
| [docs/SAFE_PROFESSIONALIZATION_PLAN.md](../docs/SAFE_PROFESSIONALIZATION_PLAN.md) | Full cleanup playbook |
| [docs/INTERVIEW_DEMO_CHECKLIST.md](../docs/INTERVIEW_DEMO_CHECKLIST.md) | Demo smoke tests |

**Status:** All three machines on `main` @ `cd6b493`+; large **untracked** Growflow + Kylo debug trees still on disk.

### 2. Project Kylo — forensic audit (transaction revision tracking)

| Doc | Purpose |
|-----|---------|
| [products/project-kylo/docs/AUDIT_SYSTEM.md](../products/project-kylo/docs/AUDIT_SYSTEM.md) | Audit system overview |
| [products/project-kylo/docs/ORCHESTRATOR_REPORT_2026-07-10.md](../products/project-kylo/docs/ORCHESTRATOR_REPORT_2026-07-10.md) | Posting freeze + readiness gates |
| [products/project-kylo/docs/OPERATIONS_RUNBOOK.md](../products/project-kylo/docs/OPERATIONS_RUNBOOK.md) | Start/stop, dry-run, kill switches |
| [products/project-kylo/docs/audit/BACKLOG-2026-TXN-002-accountant-report.md](../products/project-kylo/docs/audit/BACKLOG-2026-TXN-002-accountant-report.md) | CPA case (8 flagged 2026 rows) |

**Safety:** `runtime.mode: audit`, `posting.sheets.apply: false` — **do not re-enable posting** without runbook checklist.

**Start watchers (audit only, writes highlights/notes):**
```powershell
cd E:\Repos\products\project-kylo
.\scripts\active\start_watchers_by_year.ps1 -IntervalSecs 300
```

**Validate only (no sheet writes):**
```powershell
cd E:\Repos\products\project-kylo
$env:PYTHONPATH="."
python bin/validate_config.py
python -m pytest scaffold/tests/posting/ scaffold/tests/audit/ scaffold/tests/intake/ -v --noconftest
```

### 3. Growflow Retail Command Center — active build

| Doc | Purpose |
|-----|---------|
| [products/growflow/docs/RETAIL_COMMAND_CENTER_RUNBOOK.md](../products/growflow/docs/RETAIL_COMMAND_CENTER_RUNBOOK.md) | Full stack startup |
| [products/growflow/.cursor/plans/retail_dashboard_replica_dc39824b.plan.md](../products/growflow/.cursor/plans/retail_dashboard_replica_dc39824b.plan.md) | Implementation plan + todos |

**One-command stack (3 PowerShell windows):**
```powershell
cd E:\Repos\products\growflow
.\scripts\start_retail_command_center.ps1
```

Then open: **http://127.0.0.1:5173/** → Retail tab

**Rebuild data (if dashboard empty):**
```powershell
cd E:\Repos\products\growflow
$env:PYTHONPATH="."
python scripts/ingest_growflow_facts.py --days 30
python scripts/build_retail_dashboard.py --preset last_30_days --compare --strict --reconcile
python scripts/build_retail_capital.py
python scripts/build_retail_consignment.py
```

---

## Key files to pin in editor

**Kylo audit**
- `products/project-kylo/config/global.yaml`
- `products/project-kylo/services/audit/tick.py`
- `products/project-kylo/data/audit/kylo_2026_transactions_backlog.yaml`

**Growflow retail**
- `products/growflow/dashboard/backend/main.py`
- `products/growflow/lib/retail_dashboard/metrics.py`
- `products/ai-lab/command-center/command-center/frontend/src/components/RetailPanel.jsx`

**Repo hygiene**
- `docs/PHASES_2-6_RESULTS.md`

---

## Ports (local)

| Port | Service |
|------|---------|
| 5173 | Command Center UI (Vite) |
| 8000 | ai-lab API |
| 8791 | Growflow Retail API |
| 5433 | Kylo Postgres (Docker on power-1; not on Acheron) |

---

## Remote machines (Tailscale)

| Host | SSH | Role |
|------|-----|------|
| Acheron | local | Dev / orchestration |
| power-1 | `gregw@power-1` | Kylo production Docker |
| worker-node | `worker@worker-node` | GPU worker |

Verify power-1 Kylo: `products/ai-lab/scripts/verify_power1_production.ps1`

---

## Still open / next steps

1. Commit untracked Kylo audit artifacts (`AUDIT_SYSTEM.md`, backlog YAML, `apply_audit_backlog.py`)
2. Commit or gitignore Growflow BI/dashboard WIP
3. Verify power-1 Kylo config matches audit freeze
4. CPA review of BACKLOG-2026-TXN-002
5. Drop old git stashes (`phase1-pre-main-merge-*`, `pro-sync-*`)
