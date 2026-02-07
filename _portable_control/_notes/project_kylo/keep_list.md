# Project-Kylo Keep List

**Analysis Date:** 2026-01-27  
**Root Path:** `D:\Project-Kylo\`

---

## Must Keep Items (Top 20)

### 1. `.git/` - Repository History
**Priority:** CRITICAL  
**Reason:** Git repository with full history. Never delete.

### 2. `pyproject.toml`
**Priority:** CRITICAL  
**Reason:** Python package definition, entrypoint configuration, build metadata.

### 3. `requirements.txt` + `requirements-kafka.txt`
**Priority:** CRITICAL  
**Reason:** Python dependency specifications. Required for environment setup.

### 4. `kylo-dashboard/package.json`
**Priority:** CRITICAL  
**Reason:** Node.js dependencies for Electron dashboard. Required for dashboard build.

### 5. `docker-compose.yml` + `docker-compose.kafka.yml` + `docker-compose.kafka-consumer.yml`
**Priority:** CRITICAL  
**Reason:** Service definitions for PostgreSQL, Kafka, and consumers. Core infrastructure.

### 6. `config/` (entire directory)
**Priority:** CRITICAL  
**Reason:** All configuration files (YAML, JSON). Contains company configs, instance configs, DSN maps, CSV processor config.

### 7. `kylo/` (entire directory)
**Priority:** CRITICAL  
**Reason:** Core Kylo package - CLI entrypoint, hub, watcher runtime. Main application code.

### 8. `services/` (entire directory)
**Priority:** CRITICAL  
**Reason:** Service modules (bus, intake, mover, posting, rules, triage, webhook). Core business logic.

### 9. `db/ddl/` (entire directory)
**Priority:** CRITICAL  
**Reason:** Database schema migrations (0001-0014, company migrations). Required for database setup.

### 10. `scripts/` (operational scripts)
**Priority:** HIGH  
**Reason:** PowerShell scripts for starting/stopping services, monitoring, GUI helpers. Operational tooling.

### 11. `bin/` (utility scripts)
**Priority:** HIGH  
**Reason:** Executable utilities (hub runner, watcher, CSV intake, validators). Operational tools.

### 12. `telemetry/emitter.py`
**Priority:** HIGH  
**Reason:** Used by runtime and Docker build (per README). Telemetry functionality.

### 13. `pg_hba_fixed.conf`
**Priority:** HIGH  
**Reason:** PostgreSQL HBA configuration, referenced in docker-compose.yml. Runtime-critical.

### 14. `data/layouts/` (not `layout/`)
**Priority:** HIGH  
**Reason:** Layout JSON files for companies. Active data directory. (Note: `layout/` is duplicate - see archive candidates)

### 15. `workflows/` (entire directory)
**Priority:** HIGH  
**Reason:** n8n workflow definitions and telemetry workflows. Integration definitions.

### 16. `docs/` (entire directory)
**Priority:** HIGH  
**Reason:** 29 documentation files including runbooks, guides, technical specs. Operational knowledge.

### 17. `README.md`, `COMMAND_REFERENCE.md`, `MAINTENANCE.md`
**Priority:** HIGH  
**Reason:** Primary documentation for repository, commands, and maintenance procedures.

### 18. `.github/workflows/ci.yml`
**Priority:** MEDIUM  
**Reason:** CI/CD pipeline definition. Automation infrastructure.

### 19. `scaffold/` (template code)
**Priority:** MEDIUM  
**Reason:** Template for generating new company pipelines. Development tooling.

### 20. `syncthing_monitor/`
**Priority:** MEDIUM  
**Reason:** Monitoring utility with .env configuration. Operational tooling.

---

## Probably Archive Candidates (Top 20) — DO NOT DELETE

### 1. `layout/` (entire directory)
**Status:** ARCHIVE CANDIDATE  
**Reason:** Duplicate of `data/layouts/`. Contains same 2025 JSON files (710-2025.json, jgd-2025.json, nugz-2025.json, puffin-2025.json).  
**Risk:** LOW - Verify `data/layouts/` is the active location before archiving.

### 2. `tools/scripthub_legacy/` (entire directory)
**Status:** ARCHIVE CANDIDATE  
**Reason:** Marked as legacy in README. Contains old ScriptHub implementation, duplicate config files, dated log files.  
**Risk:** LOW - Legacy code, but may have historical value or reference implementations.

### 3. `db/rules_snapshots/*_rules.sql` (non-fixed versions)
**Status:** ARCHIVE CANDIDATE  
**Files:**
- `710_empire_rules.sql`
- `jgd_rules.sql`
- `nugz_rules.sql`
- `puffin_pure_rules.sql`  
**Reason:** Have "_fixed" variants that likely supersede these.  
**Risk:** MEDIUM - Verify "_fixed" versions are actually used before archiving originals.

### 4. `bin/load_main_worksheet_rules.py` (non-fixed)
**Status:** ARCHIVE CANDIDATE  
**Reason:** Has `load_main_worksheet_rules_fixed.py` variant.  
**Risk:** MEDIUM - Verify which version is actually used.

### 5. `bin/update_nugz_main_active.py` (non-fixed)
**Status:** ARCHIVE CANDIDATE  
**Reason:** Has `update_nugz_main_active_fixed.py` variant.  
**Risk:** MEDIUM - Verify which version is actually used.

### 6. `tools/tests_manual/` (entire directory)
**Status:** ARCHIVE CANDIDATE  
**Reason:** 15+ manual/integration test files. May be superseded by `scaffold/tests/` or kept for reference.  
**Risk:** LOW - Tests are typically safe to archive if not actively run.

### 7. `tools/debug/` (entire directory)
**Status:** ARCHIVE CANDIDATE  
**Reason:** 12 debug scripts. Development/debugging tools, not runtime-critical.  
**Risk:** LOW - Debug scripts can be archived but may be useful for troubleshooting.

### 8. `tools/ops_oneoffs/` (entire directory)
**Status:** ARCHIVE CANDIDATE  
**Reason:** 3 one-off operational scripts. Historical operational tasks.  
**Risk:** LOW - One-off scripts are typically safe to archive.

### 9. `bin/` scripts with multiple variants
**Status:** ARCHIVE CANDIDATE  
**Files with potential duplicates/superseded versions:**
- `check_banner_rows.py` + `check_banner_rows_detailed.py` + `check_banner_rows_extended.py`
- `check_nugz_pending.py` + `check_nugz_pending_count.py`
- `update_nugz_active.py` + `update_nugz_main_active.py` + `update_nugz_main_active_fixed.py`  
**Reason:** Multiple variants suggest evolution/refinement. Older versions may be obsolete.  
**Risk:** MEDIUM - Need to verify which versions are actively used.

### 10. `scripts/auto_start_kylo.ps1` vs `auto_start_kylo_simple.ps1`
**Status:** ARCHIVE CANDIDATE  
**Reason:** Two auto-start scripts. "Simple" variant may supersede original.  
**Risk:** LOW - Verify which is used in production.

### 11. `tools/scripthub_legacy/logs/` (if exists)
**Status:** ARCHIVE CANDIDATE  
**Reason:** Dated log files (gitignored). Historical logs.  
**Risk:** LOW - Logs are typically safe to archive/delete.

### 12. `tools/scripthub_legacy/config/layout_map.json`
**Status:** ARCHIVE CANDIDATE  
**Reason:** Duplicate of `scripts/config/layout_map.json`. Legacy location.  
**Risk:** LOW - Verify active location is `scripts/config/`.

### 13. `db/tmp_rules/` (entire directory)
**Status:** ARCHIVE CANDIDATE  
**Reason:** Temporary rule files (kylo_jgd.sql, kylo_nugz.sql, kylo_puffin.sql). May be temporary or staging area.  
**Risk:** MEDIUM - Verify if these are actively used or truly temporary.

### 14. `scaffold/example.env`
**Status:** ARCHIVE CANDIDATE  
**Reason:** Example template file. May be useful for reference but not runtime-critical.  
**Risk:** LOW - Template files are safe to archive.

### 15. `config/companies.example.json`
**Status:** ARCHIVE CANDIDATE  
**Reason:** Example template file. Reference only.  
**Risk:** LOW - Template files are safe to archive.

### 16. `docs/n8n/` (if contains duplicate creds)
**Status:** ARCHIVE CANDIDATE  
**Reason:** Contains `pg_cred.json` and `pg_creds.json` (potential duplicate). May contain sensitive data.  
**Risk:** MEDIUM - Verify if credentials are still needed or if duplicates exist.

### 17. `scripts/sync_state.json`
**Status:** ARCHIVE CANDIDATE  
**Reason:** State file, may be runtime-generated or historical.  
**Risk:** MEDIUM - Verify if this is generated at runtime or manually maintained.

### 18. `kylo-dashboard/README.md` (if duplicate of main README)
**Status:** ARCHIVE CANDIDATE  
**Reason:** Dashboard-specific readme. May be redundant if main README covers it.  
**Risk:** LOW - Documentation redundancy is typically safe.

### 19. `scaffold/README.md` (if duplicate)
**Status:** ARCHIVE CANDIDATE  
**Reason:** Scaffold-specific readme. May be redundant.  
**Risk:** LOW - Documentation redundancy is typically safe.

### 20. `bin/watch.ps1` (if superseded by Python scripts)
**Status:** ARCHIVE CANDIDATE  
**Reason:** PowerShell watcher script. May be superseded by `bin/watch_all.py` or `kylo/watcher_runtime.py`.  
**Risk:** MEDIUM - Verify if PowerShell version is still used.

---

## Notes on Risky Items to Move

### HIGH RISK - Do Not Move Without Verification

1. **`config/` directory**
   - **Risk:** Contains active runtime configuration
   - **Action:** Verify all configs are actively used before moving anything
   - **Note:** Company configs, instance configs, DSN maps are runtime-critical

2. **`db/rules_snapshots/` (any files)**
   - **Risk:** May be referenced by migration scripts or runtime code
   - **Action:** Search codebase for references before archiving
   - **Note:** "_fixed" variants may be the active ones, but verify

3. **`bin/` scripts with "_fixed" variants**
   - **Risk:** May be called by operational scripts or automation
   - **Action:** Search for script references in PowerShell scripts and Python code
   - **Note:** Verify which variant is actually executed

4. **`data/layouts/` vs `layout/`**
   - **Risk:** Code may reference either location
   - **Action:** Search codebase for `layout/` and `data/layouts/` references
   - **Note:** One is likely the active location, but verify before archiving

5. **`telemetry/emitter.py`**
   - **Risk:** Referenced in README as used by runtime and Docker build
   - **Action:** DO NOT MOVE - Keep in place per README instructions

6. **`pg_hba_fixed.conf`**
   - **Risk:** Referenced in docker-compose.yml volume mount
   - **Action:** DO NOT MOVE - Required at current location for Docker

### MEDIUM RISK - Verify Before Moving

1. **`tools/scripthub_legacy/`**
   - **Risk:** May contain reference implementations or historical logic
   - **Action:** Review for any unique logic before archiving
   - **Note:** Marked as legacy, but may have value

2. **`scripts/config/` vs `tools/scripthub_legacy/config/`**
   - **Risk:** Duplicate configs may be used by different systems
   - **Action:** Verify which location is actively used by ScriptHub vs Kylo scripts

3. **`db/tmp_rules/`**
   - **Risk:** May be staging area for active rule development
   - **Action:** Verify if these are temporary or actively used

### LOW RISK - Generally Safe to Archive

1. **`tools/debug/`** - Debug scripts, not runtime-critical
2. **`tools/ops_oneoffs/`** - Historical one-off scripts
3. **`tools/tests_manual/`** - Manual tests, not part of CI/CD
4. **Example/template files** - Reference only, not runtime-critical

---

## Archive Heuristics Applied

### High Value Indicators (KEEP)
- ✅ Contains `.git` → KEEP
- ✅ Contains `pyproject.toml` → KEEP
- ✅ Contains `requirements.txt` → KEEP
- ✅ Contains `package.json` → KEEP
- ✅ Contains `docker-compose.yml` → KEEP

### Archive Candidate Indicators
- ⚠️ Named "old", "backup", "copy", "final" → None found
- ⚠️ Named "v1/v2/v3" → None found
- ⚠️ Dated folders → Year-based configs (2025, 2026) are ACTIVE, not archive candidates
- ⚠️ "_fixed" suffix → Originals are archive candidates (verify which is active)
- ⚠️ "legacy" in name → `tools/scripthub_legacy/` is archive candidate
- ⚠️ Duplicate folders → `layout/` vs `data/layouts/` (archive `layout/`)

---

## Recommendations

1. **Before archiving anything:**
   - Search codebase for file/folder references
   - Check PowerShell scripts for hardcoded paths
   - Verify Docker volume mounts
   - Review CI/CD workflows for references

2. **Safe first archive candidates:**
   - `layout/` (after verifying `data/layouts/` is active)
   - `tools/debug/` (debug scripts)
   - `tools/ops_oneoffs/` (one-off scripts)
   - Example/template files

3. **Verify before archiving:**
   - `db/rules_snapshots/*_rules.sql` (non-fixed versions)
   - `bin/` scripts with "_fixed" variants
   - `tools/scripthub_legacy/` (may have reference value)

4. **Do not archive:**
   - Any files in `config/`, `kylo/`, `services/`
   - `telemetry/emitter.py`
   - `pg_hba_fixed.conf`
   - Any docker-compose files
   - Package definition files (pyproject.toml, requirements.txt, package.json)
