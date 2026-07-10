# Kylo Operations Runbook

**Updated:** 2026-07-10  
**Status labels:** Implemented | Planned | Deprecated

---

## 1. Machine roles

| Machine | Role | Kylo path | Status |
|---------|------|-----------|--------|
| Acheron | Dev / orchestration | `E:\Repos\Project-Kylo` | Implemented |
| power-1 (CAMERASERVER) | Primary production worker | `C:\Project-Kylo` | Implemented |
| worker-node | GPU / worker_assistant | `C:\worker\repos\Project-Kylo` | Kylo deprecated here |

---

## 2. Startup (development — safe / audit mode)

**Implemented.** Use the active watcher script:

```powershell
cd E:\Repos\Project-Kylo
.\scripts\active\start_watchers_by_year.ps1 -IntervalSecs 300
```

This starts:

- `KYLO_2025` and `KYLO_2026` watchers
- Env: `KYLO_READ_ONLY=1`, `KYLO_RUNTIME_MODE=audit`, `KYLO_CONFIG_PATH=config/global.yaml`

**Logs:**

- `.kylo/instances/KYLO_2025/logs/watcher.log`
- `.kylo/instances/KYLO_2026/logs/watcher.log`
- `.kylo/instances/<id>/logs/audit.log`

**Optional sync runner:** `tools/scripthub_legacy/sync_runner.py` (if present).

---

## 3. Startup (production — power-1)

**Planned operator procedure** (not auto-executed):

```powershell
# On power-1 (or via ai-lab remote scripts):
cd C:\Project-Kylo
# Confirm config BEFORE start:
#   runtime.mode: post
#   posting.sheets.apply: true
#   KYLO_ALLOW_POST=1
.\ai-lab\scripts\_power1_kylo_start.ps1   # or org-specific task
```

Verify: `ai-lab/scripts/verify_power1_production.ps1`

---

## 4. Shutdown

### Development watchers

- Close PowerShell windows started by `start_watchers_by_year.ps1`, or
- `Stop-Process -Id <pid>` using PIDs in `.kylo/startup/background_jobs.json`

### Production (power-1)

- Stop scheduled tasks / Docker stack per `_power1_restart_docker_kylo.ps1` documentation
- **Do not** truncate databases

---

## 5. Dry-run mode

**Implemented.** Multiple independent gates (any one disables value writes):

| Control | Location |
|---------|----------|
| `posting.sheets.apply: false` | `config/global.yaml` |
| `runtime.mode: audit` | `config/global.yaml` |
| `KYLO_READ_ONLY=1` | Environment |
| `KYLO_SHEETS_DRY_RUN=1` | Environment |
| `runtime.dry_run: true` | Config |

**Single-tick smoke test:**

```powershell
$env:PYTHONPATH = "E:\Repos\Project-Kylo"
$env:KYLO_INSTANCE_ID = "KYLO_2026"
$env:KYLO_CONFIG_PATH = "config/global.yaml"
$env:KYLO_READ_ONLY = "1"
$env:KYLO_SHEETS_DRY_RUN = "1"
$env:KYLO_AUDIT = "0"   # optional: skip highlight/note writes
python -m bin.watch_all --years 2026 --instance-id KYLO_2026 --once
```

Expect log line: `[POSTING] dry_run=True` and `Writes DISABLED`.

---

## 6. Forensic audit mode

**Implemented.** Default in `config/global.yaml`:

```yaml
runtime:
  mode: audit
audit:
  enabled: true
  apply_highlights: true
  write_notes: true
```

- Snapshots: `.kylo/instances/<id>/snapshots/`
- Diff log: `.kylo/instances/<id>/logs/audit.log`
- **Note:** Audit mode still writes highlights/notes to intake sheets unless disabled.

Apply backlog manifest:

```powershell
python bin/apply_audit_backlog.py --manifest data/audit/kylo_2026_transactions_backlog.yaml --dry-run
```

---

## 7. Production enablement checklist

**Blocked until gates pass.** All must be true:

- [ ] Posting fix deployed on power-1 (same commit as local tests)
- [ ] `scaffold/tests/posting/test_incremental_posting.py` passes on power-1
- [ ] 2026 backlog reviewed with CPA
- [ ] Dry-run watcher on power-1 shows expected cell plan, zero unintended writes
- [ ] `posting.mark_posted` decision documented (currently `false` = no Column F updates)
- [ ] Executive approval recorded
- [ ] Set `runtime.mode: post`, `posting.sheets.apply: true`, `KYLO_ALLOW_POST=1`
- [ ] Remove `KYLO_READ_ONLY` / `KYLO_SHEETS_DRY_RUN`
- [ ] First live tick monitored; rollback plan ready (Section 6 of orchestrator report)

---

## 8. Emergency kill switches

| Action | Command / config |
|--------|------------------|
| Immediate read-only | `$env:KYLO_READ_ONLY = "1"` + restart watcher |
| Disable posting config | `posting.sheets.apply: false` in global.yaml |
| Audit-only | `runtime.mode: audit` |
| Disable one instance | `$env:KYLO_DISABLE_POSTING_FOR = "KYLO_2026"` |
| Disable one company | `$env:KYLO_DISABLE_POSTING_COMPANIES = "JGD"` |
| Circuit breaker | Automatic after consecutive failures (`runtime.circuit_breaker`) |

---

## 9. Validation commands

```powershell
cd E:\Repos\Project-Kylo
$env:PYTHONPATH = "."
python bin/validate_config.py
python -m pytest scaffold/tests/posting/ scaffold/tests/audit/ scaffold/tests/intake/ -v --noconftest
```

---

## 10. Deprecated / planned

| Item | Status |
|------|--------|
| CREDIT CARDS intake tab | Deprecated |
| Legacy rules tab names (`Pending Rules –`) | Deprecated |
| worker-node as Kylo host | Deprecated (migrated to power-1) |
| Kafka full fan-out production | Planned — see `KAFKA_EVENT_BUS_RUNBOOK.md` |
| n8n master workflow | Planned / optional |
