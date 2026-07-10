# Executive Summary — Project Kylo

**Updated:** 2026-07-10 (multi-agent orchestrator audit)  
**Previous review:** 2025-01-15 (superseded for readiness claims)

---

## Current status: NOT READY FOR PRODUCTION

Kylo’s **posting logic fix** (full cell totals + removed 90% auto-reprocess) is **implemented and unit-tested** on the Acheron dev machine. **Live transaction posting is frozen** locally. **Production readiness is blocked** until power-1 is audited, code is synced, and 2026 forensic backlog is CPA-cleared.

**Best current label:** **READY FOR FURTHER DRY-RUN TESTING**

---

## What was verified (2026-07-10)

| Check | Result |
|-------|--------|
| `posting.sheets.apply: false` + `runtime.mode: audit` | Confirmed (global + kylo.config after safety freeze) |
| Posting fix in `jgdtruth_poster.py` | Confirmed (`matched_writes` / `pending_writes`) |
| Unit tests (posting, audit, intake) | **23/23 passed** |
| `bin/validate_config.py` | Passed |
| Local Kylo processes | None running (only unrelated python script) |
| SSH to power-1 / worker-node | Reachable |

## What was NOT verified

| Gap | Impact |
|-----|--------|
| power-1 Docker / watcher processes | Unknown production state |
| power-1 `posting.sheets.apply` on deployed copy | May still be `true` with pre-fix code |
| Postgres on power-1:5433 from Acheron | Not reachable (Tailscale/firewall) |
| Integration tests with live DB | Not run |
| Git monorepo hygiene | 600+ dirty paths; branch drift across machines |

---

## Root cause summary (2026 posting incidents)

1. **Partial target totals** — only unposted intake rows were summed into financial cells.
2. **Aggressive reprocess** — heuristic re-ran large portions of the sheet unnecessarily.
3. **`mark_posted` timing** — marking intake before verifying targets could mask drift (mitigated by verify path; currently `mark_posted: false` during freeze).

---

## Safety freeze applied

`config/kylo.config.yaml` aligned with `config/global.yaml`:

- `runtime.mode: audit`
- `posting.sheets.apply: false`
- `posting.mark_posted: false`

**Rollback:** see `docs/ORCHESTRATOR_REPORT_2026-07-10.md` Section 6.

---

## Documentation index (authoritative 2026)

| Document | Purpose |
|----------|---------|
| [ORCHESTRATOR_REPORT_2026-07-10.md](ORCHESTRATOR_REPORT_2026-07-10.md) | Full 23-section gate report |
| [OPERATIONS_RUNBOOK.md](OPERATIONS_RUNBOOK.md) | Startup, shutdown, dry-run, production enablement |
| [ARCHITECTURE_AND_DATA_FLOW.md](ARCHITECTURE_AND_DATA_FLOW.md) | Technical architecture + 35-step flow |
| [INVESTOR_CPA_DEMO.md](INVESTOR_CPA_DEMO.md) | Demo script (read-only) |
| [INCREMENTAL_POSTING.md](INCREMENTAL_POSTING.md) | Signatures, CLI, source tab fill |
| [README.md](README.md) | Doc index |

---

## Recommendation

**Do not enable production posting** until:

1. power-1 config + code audit confirms fix deployed  
2. Dry-run watcher on power-1 validates write plan  
3. 2026 audit backlog reconciled with CPA  
4. Explicit approval to set `KYLO_ALLOW_POST=1`

---

*Supersedes the 2025-01-15 "PRODUCTION READY" assessment.*
