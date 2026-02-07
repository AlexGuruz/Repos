# Obsidian Plugins Setup

## Execution Order

1. Enable Community plugins in Obsidian
2. Run the install script
3. Restart Obsidian
4. Configure Shell Commands (Run Sync, Backfill commands)
5. Configure Breadcrumbs (Folder hierarchy)
6. Configure Obsidian Git (commit settings)
7. Open [[20_projects/_project-index-dataview|Project Index (Dataview)]] to verify Dataview

---

## 1. Enable Community Plugins

1. Open **Settings** (gear icon)
2. Go to **Community plugins**
3. Click **Turn on** if it is currently off

---

## 2. Run Install Script

In PowerShell (Run as Administrator if needed for execution policy):

```powershell
powershell -ExecutionPolicy Bypass -File "E:\Repos\_scripts\install_obsidian_plugins.ps1"
```

Or, if execution policy allows:

```powershell
& "E:\Repos\_scripts\install_obsidian_plugins.ps1"
```

**Restart Obsidian** after the script completes.

---

## 3. Shell Commands Configuration

Add these commands in **Settings > Shell commands > Add new command**.

### Run Sync (RunOnce)

| Field   | Value |
|--------|-------|
| ID     | `RunSync` |
| Name   | Run Sync |
| Shell command | `powershell -ExecutionPolicy Bypass -File "E:\Repos\_scripts\repo_obsidian_sync.ps1" -RunOnce` |

### Backfill

| Field   | Value |
|--------|-------|
| ID     | `Backfill` |
| Name   | Backfill |
| Shell command | `powershell -ExecutionPolicy Bypass -File "E:\Repos\_scripts\repo_obsidian_sync.ps1" -Backfill` |

### Backfill Dry Run

| Field   | Value |
|--------|-------|
| ID     | `BackfillDryRun` |
| Name   | Backfill Dry Run |
| Shell command | `powershell -ExecutionPolicy Bypass -File "E:\Repos\_scripts\repo_obsidian_sync.ps1" -Backfill -DryRun` |

### Optional: Buttons Link

To trigger Run Sync from a note, use a button block:

```markdown
[Run Sync](obsidian://shell-commands/?execute=RunSync)
```

Requires the Shell Commands plugin and a command with ID `RunSync`.

---

## 4. Breadcrumbs Configuration

For the mirrored folder structure (`20_projects/Project/Subfolder`), Breadcrumbs works best with **Folder** hierarchy.

1. Go to **Settings > Breadcrumbs**
2. Set **Hierarchy type** to **Folder** (or adjust as needed for your graph)

---

## 5. Obsidian Git Configuration

Configure in **Settings > Obsidian Git**:

- **Commit message** – e.g. "vault backup"
- **Auto backup interval** – optional (e.g. 10 minutes)
- **Git author** – your name and email

The plugin manages its own config file; no manual JSON editing required.

---

## Recommended Plugins (installed by script)

| Plugin           | ID                     | Purpose                              |
|------------------|------------------------|--------------------------------------|
| Dataview         | dataview               | Query notes (e.g. Project Index)     |
| Breadcrumbs      | breadcrumbs            | Hierarchy / graph navigation         |
| Obsidian Git     | obsidian-git           | Vault backup to Git                  |
| Advanced Tables  | table-editor-obsidian  | Table editing                        |
| Tag Wrangler     | tag-wrangler           | Tag management                       |
| Buttons          | buttons                | Execute commands from notes          |
| Graph Analysis   | graph-analysis         | Graph metrics                        |
| Omnisearch       | omnisearch             | Full-text search                     |
| Templater        | templater-obsidian     | Templates                            |
| Shell commands   | obsidian-shellcommands | Run external commands (e.g. Sync)    |
