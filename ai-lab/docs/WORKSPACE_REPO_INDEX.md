# Workspace repository index

One master file covering important repos under `E:\Repos` plus adjacent roots you commonly use. Paths use Windows style unless noted.

For a **per-repo one-pager**, copy the section template at the bottom into `summaries/repos/<repo-name>.md` and trim to that repo only.

---

## ai-lab

**Repo:** `E:\Repos\ai-lab`  
**Purpose:** Multi-rig AI operations: main rig orchestration + governance, worker rig (SSH/Ollama), operator UI (command center), agents, registry, memory, policy, observability.

**Top-level structure**


| Path                                                             | Role                                                                                           |
| ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `brain/`                                                         | Orchestrator, execution, approvals, planner, SSH worker, tool registry, LLM client             |
| `agents/`                                                        | Specialized agents (cartographer, librarian, docsync, rag_builder, ops_watcher, etc.)          |
| `registry/`                                                      | `scripts.json`, `repos.json`, workflows, services, integrations                                |
| `memory/`                                                        | JSON state: preferences, trust, workflows, project state                                       |
| `policy/`                                                        | YAML autonomy and allow/block lists                                                            |
| `docs_source/`                                                   | Canonical docs: `DOCUMENTATION_STANDARD.md`, `WORKER_CURRENT.md`, `SSH_SETUP.md`, `contracts/` |
| `command-center/command-center/`                                 | Operator app: Vite/React UI + FastAPI backend + WebSocket                                      |
| `scripts/`                                                       | `start.ps1`, `stop.ps1`, worker tunnel, prepared context refresh, GitHub sync, personal ops    |
| `tests/`                                                         | pytest for core brain/agents/router/worker                                                     |
| `chat_ui/`                                                       | Flask chat UI (`python -m chat_ui.app`)                                                        |
| `observability/`                                                 | `collect_health.py`, `health.json`, service/security artifacts                                 |
| `email_sorter/`                                                  | Email pipeline pieces; `gmail_portable/` minimal Gmail client for checkout                     |
| `m6b-docsync/`                                                   | Docsync subproject                                                                             |
| `Ai/`                                                            | Large subtree: experiments, upstream-style agent repos, internal roadmaps/schemas              |
| `config/`, `lib/`, `tools/`, `ops/`, `state/`, `sessions.sqlite` | Supporting config, libraries, ops, runtime state                                               |
| `secrets/` (if present)                                          | Local secrets; prefer not committing; align with `.gitignore`                                  |


**Important paths**

- UI/API: `command-center/command-center/` — see `README.md`, `BOOT.md`
- Contracts: `docs_source/contracts/`
- Tests: `TESTING.md`, `pytest.ini`

**Run / build / deploy**

- Recommended: `.\scripts\start.ps1` (use `-LocalOnly` to skip governance repo coupling); UI `http://localhost:5173`, API `http://127.0.0.1:8000`
- Stop: `.\scripts\stop.ps1`
- CLI: `python -m brain.orchestrator.main "<query>"`
- Health: `python observability/collect_health.py`
- Tests: `python -m pytest tests/ -v` from repo root; backend tests under `command-center/command-center/backend/`

**Conventions**

- Prefer `registry/scripts.json` and existing workflows before new automation
- High observability, low authority: writes/exec policy-gated
- Worker constants documented in `README.md` and `docs_source/WORKER_CURRENT.md`

**Known traps**

- Command center and ai-lab tests are separate pytest trees (`TESTING.md`)
- Worker SSH/Ollama hosts must match `WORKER_CURRENT.md` or orchestration assumptions drift
- `Ai/` is large; `.cursorignore` / indexing may exclude parts

**Status / notes**

- Primary “hub” repo for this workspace; keep `docs_source/` in sync with behavior changes

---

## ai-lab-governance

**Repo:** `E:\Repos\ai-lab-governance`  
**Purpose:** Shared control plane for Cursor + local AI: policies, registries, schemas, wrappers, bootstrap, version pin for both rigs.

**Top-level structure**


| Path                                | Role                                                                      |
| ----------------------------------- | ------------------------------------------------------------------------- |
| `policies/`                         | Approval tiers, allowlists, denied actions, memory rules, execution rules |
| `registry/`                         | Tool/repo/agent registry JSON                                             |
| `schemas/`                          | JSON Schema for approvals, actions, jobs, memory                          |
| `wrappers/`                         | `run_approved.py`, `submit_approval.py`, `log_action.py`, etc.            |
| `bootstrap/`                        | `setup_main_rig.ps1`, worker setup scripts, `verify_governance.py`        |
| `cursor/`                           | Cursor rules / prompts (bootstrap installs)                               |
| `configs/`                          | e.g. `governance_version.yaml`                                            |
| `approvals/`, `logs/`, `templates/` | Approvals artifacts, logs, templates                                      |


**Important paths**

- `README.md`, `AGENTS.md`, `GLOBAL_POLICY.md`

**Run / build / deploy**

- Env: `AI_LAB_GOVERNANCE_ROOT`, on worker `AI_LAB_MACHINE=worker`
- Bootstrap: `.\bootstrap\setup_main_rig.ps1` (main), worker variants in README
- Verify: `python bootstrap/verify_governance.py` after pulls; bump `configs/governance_version.yaml` when policy changes

**Conventions**

- Hard rule: no state-changing automation except through governance wrappers + policy here

**Known traps**

- Main and worker must stay on compatible git ref + governance version
- If `.cursorignore` cannot be installed from `cursor/`, mirror ignore rules per README

**Status / notes**

- Command center can run with `-LocalOnly` when governance path is unavailable; production operator flow expects this repo present and verified

---

## awesome-n8n-templates

**Repo:** `E:\Repos\awesome-n8n-templates`  
**Purpose:** Curated collection of third-party **n8n workflow JSON** templates (upstream-style catalog, not internal app code).

**Top-level structure**

- Category folders: `Gmail_and_Email_Automation/`, `Slack/`, `OpenAI_and_LLMs/`, `PDF_and_Document_Processing/`, etc.
- `img/`, `README.md`, `README-zh.md`, `.github/`

**Important paths**

- Browse by category; each folder holds `.json` workflow exports

**Run / build / deploy**

- No build: import JSON into self-hosted or cloud n8n
- Disclaimer in README: templates sourced online; not authored/owned by repo maintainer

**Known traps**

- Credentials and nodes must be re-bound in your n8n instance; do not trust unknown workflows blindly

**Status / notes**

- Reference / starter library, not deployed as a service from this folder alone

---

## cog-allocation-system

**Repo:** `E:\Repos\cog-allocation-system`  
**Purpose:** Sales CSV (Drive folder) → local dump → scripts → **Google Sheets** daily COG by brand (NUGZ / PUFFIN / EMPIRE tabs, helpers).

**Top-level structure**


| Path       | Role                                                                                               |
| ---------- | -------------------------------------------------------------------------------------------------- |
| `scripts/` | `drive_watcher.py`, `extract_unique_brands.py`, `calculate_daily_cog.py`, `populate_categories.py` |
| `lib/`     | `config_loader.py`, `sheets_helper.py`                                                             |
| `config/`  | `config.yaml`, optional per-repo service account path                                              |
| `data/`    | `csv_dump/`, `state/`, `logs/`                                                                     |
| `docs/`    | Pipeline and sheet mapping (`PIPELINE_AND_SHEETS.md`)                                              |
| `tools/`   | Ancillary utilities                                                                                |


**Important paths**

- `README.md` — commands and sheet IDs
- Device-wide SA: `D:\_config\google_service_account.json` or `GOOGLE_APPLICATION_CREDENTIALS`

**Run / build / deploy**

- `python scripts/drive_watcher.py` or `--run-once`; PowerShell `run_drive_watcher.ps1`
- Requires Google API credentials with Drive + Sheets access

**Known traps**

- `config/service_account.json` is local; do not commit secrets
- Sheet IDs and folder IDs in `config.yaml` must match production workbooks

**Status / notes**

- Feeds Kylo BALANCE / operational sheets per README cross-links

---

## geomapper app

**Repo:** `E:\Repos\geomapper app` (GIGATT Geomapper)  
**Purpose:** Permit/route dispatch: email poll → geocode → map UI; evolving to Supabase auth, driver app, jobs API (see `plan.md`).

**Top-level structure**


| Path                 | Role                                                                                         |
| -------------------- | -------------------------------------------------------------------------------------------- |
| `server.py`          | Main API + static `web/`                                                                     |
| `poller.py`          | IMAP / ingestion                                                                             |
| `web/`               | Frontend assets                                                                              |
| `backend/`           | Additional backend pieces as phased                                                          |
| `driver-app/`        | Capacitor iOS/Android scaffold                                                               |
| `supabase/`          | Migrations / SQL                                                                             |
| `python/`            | Optional portable Python                                                                     |
| `scripts/`, `tests/` | API tests, tooling                                                                           |
| Root docs            | `plan.md` (SSOT), `BASELINE.md`, `PHASE*_SETUP.md`, `DEPLOY.md`, `ENV_VARS.md`, `TESTING.md` |


**Important paths**

- `config.json` / `config.json.example` — Maps key, IMAP
- `Procfile`, `runtime.txt` — Railway/Render style deploy

**Run / build / deploy**

- Local: `Start GIGATT Geomapper.bat` or `start.bat` → `http://127.0.0.1:8080`
- Deploy: `DEPLOY.md` — Railway/Render `python server.py`, Supabase env vars
- Tests: `pytest tests/`, `python scripts/run_api_tests.py` (see `TESTING.md`)

**Conventions**

- Agents: follow `plan.md` execution rules and phased build order when changing behavior

**Known traps**

- Many phase-specific env vars; production needs Supabase JWT secret and URL alignment
- Repo root contains sample PDFs/GPX/CSVs; do not assume all are production data

**Status / notes**

- Active product codebase with phased roadmap; `DEPLOY_READINESS.md` for go-live gaps

---

## Gigatt Transport LLC

**Repo:** `E:\Repos\Gigatt Transport LLC`  
**Purpose:** Transport/logistics ops: invoices, route builders, email-to-maps helpers, related PDFs/GPX; Obsidian brain link in README.

**Top-level structure**


| Path                                           | Role                                                                         |
| ---------------------------------------------- | ---------------------------------------------------------------------------- |
| `gigatt-transport/`                            | Main app/package (if present as subtree)                                     |
| `gigatt-transport-frontend/`                   | Frontend subtree                                                             |
| `High Pole/`, `pevo-witpac-defensive-driving/` | Related material folders                                                     |
| Root scripts                                   | `build_exact_permit_route.py`, `send_*_email.py`, `verify_route_accuracy.py` |
| Templates / outputs                            | HTML/PDF invoice templates, sample routes                                    |


**Important paths**

- `README.md` (short); Obsidian: `E:\Ai\Obsidian\Brain\20_projects` per README

**Run / build / deploy**

- Python one-offs from repo root; no single standardized `start` documented in README

**Known traps**

- Mix of operational artifacts (PDFs, GPX) and code; keep secrets out of git

**Status / notes**

- Lightweight meta-repo + scripts; coordinate with geomapper for route stack

---

## Greg-Kylo

**Repo:** `E:\Repos\Greg-Kylo`  
**Purpose:** Transaction intake and rules-based processing for Greg (multi bank/card), forked from Project-Kylo with separate GCP identity.

**Top-level structure**


| Path                                               | Role                                  |
| -------------------------------------------------- | ------------------------------------- |
| `kylo/`, `services/`, `bin/`                       | Runtime services and CLIs             |
| `kylo-dashboard/`                                  | Dashboard app                         |
| `config/`                                          | `global.yaml`, accounts, instances    |
| `db/`, `workflows/`, `telemetry/`                  | Persistence, workflow defs, telemetry |
| `scripts/`                                         | `active/` start/stop/watchers         |
| `docker-compose*.yml`, `Dockerfile.kafka-consumer` | Stack composition                     |
| `docs/`, `tools/`, `scaffold/`                     | Docs and utilities                    |


**Important paths**

- `COMMAND_REFERENCE.md`, `MAINTENANCE.md`, `docs/README.md`
- `pyproject.toml`, `requirements.txt`
- Service account path in `config/global.yaml` (example: under `E:\secrets\gcp\...`)

**Run / build / deploy**

- `.\start_all_services.ps1`, `.\scripts\active\start_watchers_by_year.ps1`, stop scripts in README
- Postgres: port **5434**, DB `greg_kylo_global`, container **greg-kylo-pg**
- Kafka naming: `txns.greg.`*, `greg-kylo-*` to avoid Kylo collisions

**Known traps**

- Must not share GCP project with main Kylo; quota and IAM isolation by design
- `telemetry/` and `pg_hba_fixed.conf` called out as runtime-critical in README

**Status / notes**

- Production-style services repo; use provided PowerShell entrypoints

---

## Growflow

**Repo:** `E:\Repos\Growflow`  
**Purpose:** GrowFlow (cannabis POS/compliance) integration: exports, inventory, scripts feeding COG and expense tracking.

**Top-level structure**


| Path                            | Role                                        |
| ------------------------------- | ------------------------------------------- |
| `scripts/`                      | Automation, inventory, alerts, sheet pushes |
| `config/`                       | `config.example.yaml` → `config.yaml`       |
| `contracts/`                    | Integration contracts                       |
| `data/`, `exports/`, `state/`   | Local data (often gitignored)               |
| `lib/`, `tools/`, `company_bi/` | Shared libs, utilities, BI                  |
| `docs/`                         | `SETUP.md` etc.                             |
| `tests/`                        | pytest                                      |


**Important paths**

- `README.md` — NUGZ EXPENSES col 10 linkage, data flow to `cog-allocation-system`

**Run / build / deploy**

- Copy `config/config.example.yaml` to `config/config.yaml`, add credentials
- Run scripts from repo root with venv per `requirements.txt`

**Known traps**

- CSV exports and credentials are sensitive; paths to sales exports vary by machine

**Status / notes**

- Rebuilt internal integration; coordinates with Kylo/ScriptHub per README

---

## scripts (E:\Repos\scripts)

**Repo:** `E:\Repos\scripts`  
**Purpose:** Small loose **Python utilities** not tied to a single product repo.

**Top-level structure**

- `drive_folder_download.py`, `stoned_projects_invoice.py`, `invoices/`, `worker_ai/` (subset mirror of ai-lab worker helpers possible)

**Run / build / deploy**

- Ad hoc: `python <script>.py` from this directory; no unified README in tree

**Known traps**

- Not a formal package; dependencies per script only

**Status / notes**

- Scratchpad / shared scripts; consider promoting stable tools into `ai-lab/registry` or product repos

---

## Worker

**Repo:** `E:\Repos\Worker`  
**Purpose:** Appears minimal in workspace (`logs/` only at scan time) — likely log landing, stub, or partial checkout.

**Top-level structure**

- `logs/`

**Run / build / deploy**

- N/A unless populated on disk

**Known traps**

- Do not assume full worker codebase lives here; canonical worker docs in `ai-lab/docs_source/WORKER_CURRENT.md`

**Status / notes**

- Verify on your machine whether this is intentional sparse folder or needs git pull/submodule

---

## renovate (upstream clone)

**Repo:** `E:\renovate`  
**Purpose:** **Mend Renovate** open-source dependency update bot (full upstream monorepo: TS/JS tooling, docs, tests).

**Top-level structure**

- `lib/`, `package.json`, `pnpm-workspace.yaml`, `docs/`, `test/`, `.github/` — standard Renovate OSS layout

**Run / build / deploy**

- Node/pnpm per `package.json`; used for contributing or local debugging of Renovate itself — not your app deploy target

**Known traps**

- Large dependency tree; this is not the same as “turning on Renovate” in your app repos (that uses the hosted app or CE image)

**Status / notes**

- Reference/vendor-style clone unless you actively contribute

---

## secrets (local vault)

**Path:** `E:\secrets`  
**Purpose:** **Not an application repo** — local store for credentials (GCP JSON, GrowFlow, gigatt IMAP text, etc.).

**Top-level structure**

- `gcp/`, `GrowFlow/`, loose credential files

**Run / build / deploy**

- Never commit; referenced from `Greg-Kylo`, geomapper, Growflow configs via absolute paths

**Known traps**

- Back up securely; rotation requires updating every consuming `config.yaml` / env

**Status / notes**

- Treat as sensitive filesystem root; align ignores with governance `cursor/` guidance

---

## venv (optional)

**Path:** `E:\Repos\venv`  
**Purpose:** Often a **Python virtual environment** directory or shared venvs (name collision common).

**Known traps**

- Do not index in IDE if huge; confirm whether this is disposable envs vs. anything committed

---

# Section template (copy for one-repo files)

```markdown
## <repo name>

**Path:** `...`

**Purpose:** One paragraph.

**Top-level structure**
- `folder/` — ...

**Important paths**
- ...

**Run / build / deploy**
- ...

**Special conventions**
- ...

**Known traps**
- ...

**Status / notes**
- ...
```

---

*Generated for workspace orientation. Update this file when repo roles or entrypoints change.*