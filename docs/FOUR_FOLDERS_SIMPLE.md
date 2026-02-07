# What’s in the 4 Folders (Simple Breakdown)

---

## 1. **ai** (inside activepieces)

**Where:** `activepieces/packages/server/api/src/app/ai/` and related UI/docs.

**In plain terms:** Code that lets Activepieces talk to AI services (OpenAI, Google, Anthropic, Replicate, etc.).

**What’s inside:**
- **Providers** – One “adapter” per AI service (OpenAI, Google, Anthropic, Replicate) so the app can call them.
- **Types & utils** – Shared shapes and helper code for AI.
- **Controller / service / module** – API and app wiring for AI features.
- **React UI** – Setup screens where you add and configure AI providers (e.g. API keys).
- **Docs** – e.g. AI/MCP documentation.

**One line:** “AI” = **Activepieces’ AI provider and setup code** (connect and use OpenAI, etc.).

---

## 2. **git** (at repo root)

**Where:** `e:\Repos\git/`

**In plain terms:** A full **portable Git for Windows** install sitting inside your repo – the actual `git` program and tools, not a project folder.

**What’s inside:**
- **bin, cmd** – Git commands and launchers (`git.exe`, etc.).
- **git-bash.exe, git-cmd.exe** – Open Git Bash or Git CMD.
- **mingw64, usr** – Unix-style environment and tools Git uses (bash, perl, etc.).
- **etc** – Config (e.g. SSH, shell).
- **dev, tmp** – Development/temp use.
- **unins000.exe (.dat, .msg)** – Uninstaller for this Git install.
- **LICENSE.txt, ReleaseNotes.html** – Legal and release notes.

**One line:** “Git” = **The Git program itself** (portable install), not your project code.

---

## 3. **secrets** (Project-Kylo only)

**Where:** `Project-Kylo/.secrets/` (note the dot: `.secrets`).

**In plain terms:** A small folder where Kylo keeps **one important secret file** so it can write to Google Sheets.

**What’s inside:**
- **README.md** – Says: “Put your Google service account file here so Kylo can access Sheets.”
- **service_account.json** – The Google account key file (you add this; it’s not in git). Without it, Kylo can’t post to Sheets.

**One line:** “Secrets” = **Kylo’s Google login file** so it can update your Sheets.

---

## 4. **worker** (inside activepieces)

**Where:** `activepieces/packages/server/worker/`

**In plain terms:** The **background runner** that actually executes automations (flows, webhooks, scheduled jobs, etc.) when the main API says “run this.”

**What’s inside:**
- **Executors** – Who runs what: flow runs, webhooks, repeating jobs, user-interaction jobs, agent jobs.
- **Runner / process** – Starts and manages the engine process (including sandbox options).
- **Cache** – Builds and caches pieces and execution files so runs are fast.
- **Piece manager** – Loads and manages “pieces” (integrations).
- **API / job polling** – Talks to the main server and pulls the next job to run.
- **flow-worker** – Core logic that runs a flow from start to finish.

**One line:** “Worker” = **The engine that runs your automations** when something triggers them.

---

## Quick reference

| Folder  | Location              | In simple terms                          |
|---------|------------------------|------------------------------------------|
| **ai**  | inside activepieces    | AI provider and setup code (OpenAI, etc.) |
| **git** | repo root              | The Git program (portable install)      |
| **secrets** | Project-Kylo/.secrets | Google key file for Kylo → Sheets       |
| **worker** | inside activepieces  | Background runner that runs automations  |
