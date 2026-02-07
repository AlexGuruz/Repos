# What the Repos Contain (E:\Repos)

High-level inventory of what’s **in** the workspace. For what’s *missing* or external, see **docs/MISSING_FROM_REPOS.md**.

---

## Core business systems

### **cog-allocation-system**
- **Purpose:** Sales CSV → daily Cost of Goods (COG) per brand → Google Sheets (NUGZ COG, PUFFIN COG, EMPIRE COG, DROP DOWN HELPER).
- **Contains:** Python scripts (drive_watcher, calculate_daily_cog, extract_unique_brands, populate_categories), lib (config_loader, sheets_helper), config (config.yaml), data folders (csv_dump, state, logs – mostly placeholders in git). Docs: PIPELINE_AND_SHEETS, RECREATION_SPEC, SALES_CSV_EXPECTED.
- **Data flow:** Google Drive folder → csv_dump → Sheets (COG_RAW_DAILY, POS_Export, DROP DOWN HELPER).

### **Project-Kylo**
- **Purpose:** Main processing system – petty cash, BANK, transactions, watchers, posting to Google Sheets (BALANCE, company COG/expense sheets). Maintenance-only; dev paused.
- **Contains:** Services (intake, mover, posting, rules, state, etc.), `kylo/` (watcher, hub, config), `bin/` (csv_intake, watch_all, rules/Sheets tools), `config/` (global.yaml, instances, dsn_map, layout), `db/` (DDL, rules_snapshots), `scaffold/` (tests, tools), `tools/` (scripthub_legacy, scripthub/do_not_delete, ops_oneoffs, tests_manual), Docker (Postgres, Kafka/Redpanda, consumers), docs (runbooks, CSV_INTAKE, Kafka, etc.), `.secrets/` (service_account – you add). Watchers run by year (2025 / 2026).

### **Growflow**
- **Purpose:** GrowFlow integration – expense tracking (NUGZ EXPENSES col 10), sales/OrderItems export for COG (planned).
- **Contains:** README, requirements.txt, config example, docs (RECREATION_SPEC, SETUP), tools/README. **No full API client or export scripts yet** – recreation spec / TODOs only.

### **PettyCash_Migration_Package / PettyCash**
- **Purpose:** Petty cash sorter – Google Sheets integration, transaction processing, rules, backups.
- **Contains:** Python (petty_cash_sorter, google_sheets_integration, database_manager, csv_downloader, etc.), config, LOCKDOWN/BACKUPS, docs (CLAUDE.md, READMEs, migration/implementation notes). Migration package layout; production-ready docs reference `config/service_account.json` (you add).

---

## Documentation & control (workspace root and _*)

### **docs/** (workspace root)
- **SYSTEMS_OVERVIEW.md** – Architecture (GrowFlow → COG → Kylo), data paths, Sheets, original D: locations.
- **MISSING_FROM_REPOS.md** – Checklist of what’s not in git / on D: / credentials / TODOs.

### **_scripts/**
- **ORGANIZATION_LOG.md** – D:\ root organization log (2026-01-27).
- **Church/** – Tools, Youtube (e.g. youtube_to_mp4.py, lyric videos).
- **download_youtube.ps1** – YouTube download helper.

### **_portable_control/**
- Analyses and manifests for D: drive and migration: **D_DIRECTORIES_ANALYSIS.md**, **D_ROOT_FILES_ANALYSIS.md**, **D_ROOT_ORGANIZATION_COMPLETE.md**, **D_ROOT_ORGANIZATION_SUMMARY.md**, **REPO_COMPARISON_REPORT.md**, **SCRIPTHUB_CLASSIFICATION.md**.
- **Growflow Retail GraphQL API Documentation** (PDF + TXT).
- **_notes/project_kylo/** – keep_list, move_plan, repo_map.
- **_scripts/** – move/archive Kylo scripts (dry-run and execute), scan duplicates.

---

## Templates & reference

### **System Templates / Remodel-Template**
- **Purpose:** Generic Python project template – multi-entity DB, config, schema routing (Kylo-specific IDs removed).
- **Contains:** README, pytest, requirements, config examples (companies.json, dsn_map), docs (ARCHITECTURE), TEMPLATE_VERIFICATION, TEMPLATE_CLEANUP_LOG, file trees. No app code – scaffold only.

### **BMAD-METHOD**
- **Purpose:** BMAD framework – agents, tasks, checklists, templates, expansion packs (e.g. fullstack, ide, devops, creative-writing, 2d-unity).
- **Contains:** bmad-core (agents, tasks, checklists, templates, data), common utils, expansion-packs, .github (workflows, issue templates), tools (version-bump, yaml-format), CHANGELOG, CONTRIBUTING, LICENSE, README. (Nested .git was removed so contents are tracked as normal files.)

---

## Automation & workflows

### **activepieces**
- **Purpose:** Activepieces platform – automation pieces/integrations (partial clone or reference).
- **Contains:** Top-level config (tsconfig, Dockerfile, CONTRIBUTING, LICENSE, README), tools (setup-dev, update.sh). Packages (e.g. community pieces for QuickBooks, Xero, Spotify, etc.) may be present as subdirs; often added as embedded git repos.

### **awesome-n8n-templates**
- **Purpose:** Curated n8n workflow templates (JSON).
- **Contains:** AWESOME_N8N_TEMPLATES_ANALYSIS.md, categories (Instagram_Twitter_Social_Media, WordPress, etc.), JSON workflow files. Reference library for n8n.

---

## Business / one-offs (root)

### **Exzact Stat Ai business**
- **Purpose:** Business/investor materials for Exzact Stat AI.
- **Contains:** Pitch decks (PPTX, PDF), investor one-sheets, prospectus, revenue/execution plan CSV, investor_plan.xlsx, output.png. Not code – documents only.

### **Root files**
- **PASSIVE_SCRIPTS.code-workspace** – VS Code workspace.
- **README_MIGRATION.md** – Migration/setup notes (Petty Cash, credentials, etc.).
- **Enviroment_Setup.bat**, **GitPortable_Setup.bat**, **setup_migration.bat** – Setup scripts.
- **requirements.txt**, **gcloud** – Shared deps / GCP config reference.

---

## Summary table

| Area | Type | Purpose |
|------|------|--------|
| **cog-allocation-system** | App | Sales CSV → COG → Sheets |
| **Project-Kylo** | App | Petty cash, BANK, watchers, Sheets, Postgres, Kafka |
| **Growflow** | App (stub) | GrowFlow integration; TODOs |
| **PettyCash_Migration_Package** | App | Petty cash sorter, Sheets, migrations |
| **docs/** | Docs | Systems overview, missing-items checklist |
| **_scripts**, **_portable_control** | Docs + scripts | D: org log, migration/analysis, Church tools |
| **System Templates/Remodel-Template** | Template | Generic Python multi-entity template |
| **BMAD-METHOD** | Framework | BMAD agents/tasks/checklists/templates |
| **activepieces** | Automation | Activepieces pieces (partial) |
| **awesome-n8n-templates** | Reference | n8n workflow JSON templates |
| **Exzact Stat Ai business** | Assets | Investor/business docs |
