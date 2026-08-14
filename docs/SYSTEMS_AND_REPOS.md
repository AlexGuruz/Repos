# Systems & Repos — unified reference

Single map of **repos, services, ports, tunnels, and paths** for this workspace. Use it for onboarding or agent routing.

**Monorepo root:** treat paths below as relative to your clone. Define **`REPOS_ROOT`** = directory that contains `Project-Kylo`, `cog-allocation-system`, `docs`, `Ai`, etc.

| This rig (examples) | Role |
|---------------------|------|
| `C:\Repos\Repos` | Common clone location (nested `Repos` folder) |
| `E:\Repos` | Alternate drive; same layout when used |
| `C:\Repos` | Possible flat clone root |
| `C:\Project-Kylo` | Standalone Kylo checkout (may duplicate `REPOS_ROOT\products\project-kylo`) |
| `C:\worker` | Autonomous **worker** machine stack (not inside monorepo) |

If instructions say `REPOS_ROOT\…`, substitute your actual clone path.

---

## Quick lookup (systems → where → ports)

| System | Location | Ports / access | Primary docs |
|--------|----------|----------------|--------------|
| **Repos monorepo** | `REPOS_ROOT` | — | This file |
| **Project-Kylo** | `REPOS_ROOT\products\project-kylo` or `C:\Project-Kylo` | Postgres/Kafka via Docker (see Kylo README) | `Project-Kylo\README.md`, `Project-Kylo\docs\README.md` |
| **COG allocation** | `REPOS_ROOT\products\cog-allocation` | — | `cog-allocation-system\docs\PIPELINE_AND_SHEETS.md` |
| **COG (worker copy)** | `C:\worker\cog-allocation-system` | — | Same pipeline docs; optional duplicate for worker-side automation |
| **Growflow** | `REPOS_ROOT\products\growflow` (→ `products\growflow` after senior migrate) | Retail API **:8791** | `Growflow\README.md`, `Growflow\docs\`, [AI_LAB_KYLO_GROWFLOW_OVERVIEW.md](AI_LAB_KYLO_GROWFLOW_OVERVIEW.md) |
| **PettyCash** | `REPOS_ROOT\archive\pettycash-migration\PettyCash` | — | Package READMEs |
| **ai-lab** | `REPOS_ROOT\products\ai-lab` | — | `ai-lab\docs\`, `ai-lab\email_sorter\` |
| **Worker stack** | `C:\worker` | **8765** Worker Assistant, **5678** n8n, **11434** Ollama, **22** SSH | § [Worker PC stack](#worker-pc-stack) below; on-box: `C:\worker\docs\MAIN_RIG_ORCHESTRATION.md` |
| **Activepieces** | `REPOS_ROOT\vendor\activepieces` | (app-defined when run) | Upstream README; § [Glossary](#glossary-activepieces-vs-cworker) |

---

## Worker PC stack

Paths on the worker machine are under **`C:\worker`** (not the Activepieces package named “worker”).

The **worker** PC runs Ollama, Worker Assistant (FastAPI), and n8n. The **main rig** reaches them through an **SSH local port forward** (tunnel).

### Services (on worker)

| Service | Port | Purpose |
|---------|------|---------|
| **Ollama** | 11434 | Local LLM (e.g. qwen2.5-coder) |
| **Worker Assistant** | 8765 | FastAPI: health, summarize, retrieve, `index_repo` (when governance allows) |
| **n8n** | 5678 | Workflow automation / API triggers |
| **SSH** | 22 | Tunnel endpoint from main rig |

### Tunnel (from main rig)

Replace `WORKER_IP` with the worker’s LAN IP.

```bash
ssh -L 8765:localhost:8765 -L 5678:localhost:5678 -L 11434:localhost:11434 worker@WORKER_IP -N
```

### Environment (main rig, tunnel active)

```bash
export WORKER_ASSISTANT_URL=http://127.0.0.1:8765
export WORKER_N8N_URL=http://127.0.0.1:5678
export OLLAMA_HOST=127.0.0.1:11434
```

Tools on the main rig then call those URLs as if services were local.

### Supervisor (worker)

| Item | Detail |
|------|--------|
| Scheduled task | **Worker Supervisor (Worker AI)** at logon |
| Entry | `C:\worker\agents\supervisor.ps1` |
| Stop | Create `C:\worker\agents\STOP`; remove file to run again |
| Manual | `powershell -File C:\worker\agents\supervisor.ps1` |
| worker_assistant | `C:\worker\worker_ai\scripts\start_worker_assistant.ps1` (venv: `C:\worker\worker_ai\.venv`) |
| n8n | `C:\worker\agents\jobs\job_n8n_daemon.ps1` |
| Optional jobs | `kylo_watchers`, `repo_sync` — toggle `"enabled"` in `C:\worker\agents\configs\*.json` |

**Ollama:** run with `OLLAMA_HOST=0.0.0.0:11434` if the main rig uses the tunnel; open firewall for **22**, **8765**, **5678**, **11434** as needed.

**Firewall (worker, Admin):**

```powershell
powershell -ExecutionPolicy Bypass -File C:\worker\worker_ai\scripts\setup_worker_ai_firewall.ps1
```

**Health (worker):**

```powershell
C:\worker\scripts\validate_autonomous.ps1
```

```text
curl http://localhost:8765/health
```

Logs: `C:\worker\logs\supervisor.log`, state: `C:\worker\agents\state\`.

---

## Business pipeline (GrowFlow → COG → Kylo)

```
┌─────────────────┐     ┌──────────────────────────┐     ┌─────────────────────┐
│ GrowFlow / POS  │     │ cog-allocation-system    │     │ Kylo / ScriptHub    │
│ (BLEUM, etc.)   │────▶│ Sales CSV → COG by brand  │────▶│ BALANCE, NUGZ COG   │
│                 │     │ DROP DOWN HELPER         │     │ JGD EXPENSES        │
└────────┬────────┘     └──────────────────────────┘     └─────────────────────┘
         │
         │ NUGZ EXPENSES col 10 (Grow Flow subscription)
         └──────────────────────────────────────────────▶ NUGZ EXPENSES sheet
```

### COG — source & sheet targets

- **Source (CSV intake):** https://drive.google.com/drive/folders/1b1XgCjqlcS7UeGeL7oucH92xeuIwxKrP  
- **Write 1 (COG_RAW_DAILY):** spreadsheet `1GizTKLceyoVVOVAIDrODebYbCK4hRhD5Q9jZ-s0qgIs` — tab COG_RAW_DAILY  
- **Write 2 (POS_Export):** spreadsheet `1Pesnh1XQFTKPfagXgCchJQdw0te7m4L1YJAVtOPmyUs` — tab POS_Export  

Detail: `cog-allocation-system/docs/PIPELINE_AND_SHEETS.md`.

### Google Sheets (semantic)

- **BALANCE:** NUGZ COG col 6, NUGZ EXPENSES col 7, etc.  
- **NUGZ EXPENSES:** col 10 = GROW FLOW  
- **NUGZ COG, PUFFIN COG, EMPIRE COG:** daily COG by category  
- **DROP DOWN HELPER:** brands (E), categories (G), flags (H)  

### Data paths (relative to COG repo or legacy drives)

| Path | Purpose |
|------|---------|
| `cog-allocation-system/data/csv_dump/` | Input sales CSVs |
| `cog-allocation-system/data/state/` | `brand_state.json`, `cog_state.json`, `drive_watcher_state.json` |
| `D:\_data\sales_exports\` | Historical Nugz OrderItems (if D: available) |
| `D:\_config\` or `%LOCALAPPDATA%\_config\` | Device-wide `google_service_account.json` (optional) |

---

## Repos monorepo — top-level inventory

Everything below lives under **`REPOS_ROOT`** unless noted.

| Folder | Type | Purpose |
|--------|------|---------|
| **Project-Kylo** | App | Petty cash, BANK, transactions, watchers, Sheets, Postgres, Kafka/Redpanda, Docker. Maintenance-only. |
| **cog-allocation-system** | App | Sales CSV → daily COG → Sheets; Drive watcher, pipeline scripts. |
| **Growflow** | App | POS/retail intelligence, consignment, company BI, Retail API `:8791` (not a stub). |
| **PettyCash_Migration_Package** | App | Petty cash sorter, Sheets, migration assets. |
| **ai-lab** | App/tools | Email sorter, `gmail_portable`, `docs\`, tests, `brain\`. |
| **Ai** | Vault | Obsidian: `internal\obsidian-brain\Obsidian\Brain`. |
| **activepieces** | Upstream | Automation platform (partial clone). |
| **awesome-n8n-templates** | Reference | n8n workflow JSON library. |
| **BMAD-METHOD** | Framework | BMAD agents, tasks, checklists, expansion packs. |
| **System Templates** | Template | e.g. **Remodel-Template** — generic multi-entity Python scaffold. |
| **_scripts** | Scripts | Org logs, Obsidian/plugin helpers, Church tools, `download_youtube.ps1`, etc. |
| **_portable_control** | Docs/scripts | D: migration analyses, ScriptHub notes, Growflow API PDFs. |
| **docs** | Docs | **This unified guide** and indexes. |
| **Home** | Mixed | e.g. **Systems\Downloads-Manager**. |
| **Gigatt Transport LLC** | Project | Business/project files. |
| **Exzact Stat Ai business** | Assets | Decks, investor docs (not runtime code). |
| **README_MIGRATION.md**, **requirements.txt**, **PASSIVE_SCRIPTS.code-workspace**, setup `.bat` | Root | Workspace-wide migration and setup. |

**`REPOS_ROOT\Worker`:** reserved in runbooks for syncable worker config; often **absent** after clone — runtime remains **`C:\worker`** on the worker PC.

---

## Standalone / duplicate checkouts

| Path | Note |
|------|------|
| `C:\Project-Kylo` | Full Kylo tree; align with `REPOS_ROOT\products\project-kylo` when both exist (same remote, different working copies). |
| `C:\worker\cog-allocation-system` | Second copy of COG tooling for worker-side jobs; keep behavior in sync with monorepo copy intentionally. |

---

## External & legacy (often `D:\`)

| Item | Typical location |
|------|------------------|
| Sales exports | `D:\_data\sales_exports\` |
| Device config | `D:\_config\` |
| Original ScriptHub | `D:\ScriptHub` or archives under `D:\_archive\` |
| Kylo archive data | `D:\Project-Kylo\archive\data\` |
| REMODEL secrets (legacy) | `D:\REMODEL\secrets` (Kafka override docs in Kylo) |

---

## Not in Git — setup checklist

### Data (never commit)

- Sales CSVs in `csv_dump` or `D:\_data\sales_exports\` — see `cog-allocation-system/docs/SALES_CSV_EXPECTED.md`.  
- COG state JSON and logs under `cog-allocation-system/data/state`, `data/logs`.  
- Kylo instance state, `.kylo/instances/`, watcher logs.  

### Credentials

| Use | Where |
|-----|--------|
| COG / Sheets (device) | `D:\_config\google_service_account.json`, `%LOCALAPPDATA%\_config\`, or `cog-allocation-system/config/service_account.json` |
| Kylo | `products/project-kylo/.secrets/service_account.json` (or `E:/secrets/...`) |
| ScriptHub do_not_delete | `products/project-kylo/tools/scripthub/do_not_delete/config/service_account.json` |
| PettyCash | `archive/pettycash-migration/PettyCash/config/service_account.json` |
| Kylo DB / env | `products/project-kylo/.env`, optional `config/dsn_map_local.json` |

### Known gaps / TODO

- **Growflow:** API client, export to `csv_dump`/Drive, NUGZ EXPENSES col 10 automation — see `Growflow/docs/RECREATION_SPEC.md`.  
- **COG:** OrderItems column mapping / full append in `calculate_daily_cog.py` — see script and `PIPELINE_AND_SHEETS.md`.  
- **`_archive`:** may be gitignored under `REPOS_ROOT` (e.g. broken nested git).  

**Recovery quick list:** restore CSVs → add service accounts → Kylo `.env` / DSN → run COG `drive_watcher` → start Kylo Docker + watchers per `Project-Kylo\README.md`.

---

## Glossary: Activepieces vs `C:\worker`

| Term | Meaning |
|------|---------|
| **Activepieces `worker` package** | Code under `activepieces/packages/server/worker/` — **job runner inside Activepieces**, not this PC. |
| **Activepieces `ai` package** | `activepieces/packages/server/api/src/app/ai/` — provider UI for OpenAI, Google, Anthropic, etc. |
| **Autonomous worker** | **`C:\worker`** — Ollama, Worker Assistant, n8n, supervisor; see § [Worker PC stack](#worker-pc-stack). |
| **Kylo `.secrets`** | `products/project-kylo/.secrets/service_account.json` for Sheets (never commit; prefer `E:/secrets`). |

---

## Optional: portable Git folder

Some clones include a full portable **Git for Windows** tree at `REPOS_ROOT\git\` (`git.exe`, `mingw64`, etc.). **This rig’s** `REPOS_ROOT` listing may **not** include `git\` — that is normal.

---

## Monorepo Git and Obsidian

### First push (new remote)

```powershell
cd $env:REPOS_ROOT   # or cd C:\Repos\Repos
git remote add origin https://github.com/<user>/<repo>.git
git add .
git commit -m "Initial: Repos monorepo"
git branch -M main
git push -u origin main
```

Avoid pushing multi-GB folders; tune `.gitignore` first.

### Clone on another machine

Use an **empty** target directory.

```powershell
git clone https://github.com/<user>/<repo>.git C:\Repos
# or E:\Repos
```

Post-clone:

- **Obsidian vault:** `REPOS_ROOT\internal\obsidian-brain\Obsidian\Brain`  
- **Scripts:** `REPOS_ROOT\tools\scripts\_scripts\install_obsidian_plugins.ps1`, `repo_obsidian_sync.ps1` if used  
- **Secrets:** not in git — see [Not in Git](#not-in-git--setup-checklist)  
- **Worker:** runtime usually stays **`C:\worker`**; `REPOS_ROOT\Worker` may be empty — sync strategy per machine  
- **Path maps:** update `_scripts/repo_obsidian_map.json` if vault or `repos_root` differs (e.g. `C:` vs `E:`)  

| Legacy path | After consolidation |
|-------------|---------------------|
| `E:\internal\obsidian-brain\Obsidian\Brain` | `REPOS_ROOT\internal\obsidian-brain\Obsidian\Brain` |
| `E:\Worker` (optional) | `REPOS_ROOT\Worker` or parallel `C:\worker` |

---

## Related deep dives

| Topic | Document |
|-------|----------|
| Kylo operations | `Project-Kylo/COMMAND_REFERENCE.md`, `Project-Kylo/MAINTENANCE.md` |
| Kylo docs index | `Project-Kylo/docs/README.md` |
| COG pipeline | `cog-allocation-system/docs/PIPELINE_AND_SHEETS.md` |
| Email / ai-lab | `REPOS_ROOT\products\ai-lab\docs\` (runbooks, integration maps) |
| Workspace migration | `REPOS_ROOT/README_MIGRATION.md` |
| On-worker copy-paste | `C:\worker\docs\MAIN_RIG_ORCHESTRATION.md` (mirrors tunnel section; keep in sync mentally with this file) |

---

*Last consolidated: 2026-04 — replaces `SYSTEMS_OVERVIEW.md`, `REPOS_CONTENTS.md`, `MISSING_FROM_REPOS.md`, `FOUR_FOLDERS_SIMPLE.md`.*
