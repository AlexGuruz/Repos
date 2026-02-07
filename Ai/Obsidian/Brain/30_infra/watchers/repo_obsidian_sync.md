---
watcher_name: repo_obsidian_sync
target_host: local
target_type: filesystem-watcher
check_interval: 2
status: active
created: 2026-02-06
updated: 2026-02-06
---

# Watcher: repo_obsidian_sync

## Overview
Monitors E:\Repos for file/folder changes and syncs file trees plus new subfolder notes to Obsidian Brain. Uses repo_obsidian_map.json to map repo paths to Obsidian project notes.

## Target
- **Host**: local
- **Type**: filesystem-watcher
- **Endpoint/Path**: E:\Repos (or `repos_root` from config)

## Configuration

### Config file
`E:\Repos\_scripts\repo_obsidian_map.json`

### Config schema

```json
{
  "version": "1.1",
  "vault_path": "E:\\Repos\\Ai\\Obsidian\\Brain",
  "repos_root": "E:\\Repos",
  "debounce_seconds": 2,
  "defaults": {
    "create_subfolder_notes": true,
    "note_naming": "mirror",
    "ignore_patterns": [".git", "node_modules", "__pycache__", ".venv", "vendor", "dist", "build"],
    "on_folder_delete": "keep"
  },
  "mappings": [
    {
      "repo_path": "E:\\Repos\\ProjectName",
      "obsidian_project": "20_projects/ProjectName",
      "obsidian_note": "20_projects/ProjectName.md",
      "project_name": "ProjectName"
    }
  ]
}
```

### Config fields

| Field | Description |
|-------|-------------|
| `vault_path` | Obsidian Brain root |
| `repos_root` | Watched root (default E:\Repos) |
| `debounce_seconds` | Delay before processing changes |
| `defaults.create_subfolder_notes` | Create notes for new folders (true/false) |
| `defaults.note_naming` | `mirror` \| `flat` \| `slug` |
| `defaults.ignore_patterns` | Folder names to skip (case-insensitive) |
| `defaults.on_folder_delete` | `keep` \| `remove` when repo folder deleted |
| `mappings[].project_name` | Display name for notes |

### Note naming modes

| Mode | Example: repo `Contracts/2025` | Result |
|------|-------------------------------|--------|
| mirror | Mirrors repo structure | `20_projects/Project/Contracts/2025.md` |
| flat | Parent - Child | `Contracts - 2025.md` |
| slug | Full path slugified | `contracts-2025.md` |

## Sync update logic

| Event | Action |
|-------|--------|
| **Any change** under mapped repo | Update Repo Structure, Append Change Log |
| **Created** (folder) | If `create_subfolder_notes` and not ignored: create note, add link to Project Notes |
| **Deleted** (folder) | If `on_folder_delete` = `remove`: delete corresponding Obsidian note |
| **Renamed** (folder) | Rename/move Obsidian note to match new path |

## Run Commands

### Watch mode (continuous)
```powershell
powershell -File E:\Repos\_scripts\repo_obsidian_sync.ps1 -Watch
```

### One-shot (for scheduled/cron runs)
```powershell
powershell -File E:\Repos\_scripts\repo_obsidian_sync.ps1 -RunOnce
```

### Backfill (create notes for all existing subfolders)
```powershell
# Dry run: report what would be created
powershell -File E:\Repos\_scripts\repo_obsidian_sync.ps1 -Backfill -DryRun

# Execute: create notes
powershell -File E:\Repos\_scripts\repo_obsidian_sync.ps1 -Backfill
```

## Checks
- [ ] Config repo_obsidian_map.json exists
- [ ] Mapped repo paths exist
- [ ] Obsidian vault path is accessible

## Obsidian Integration

- **Project Index (Dataview)**: [[20_projects/_project-index-dataview]] — Dataview queries for project subfolders, hubs, and filtered views.
- **Shell Commands**: Add Run Sync, Backfill, and Backfill Dry Run commands via Settings > Shell commands. See [[_ops/obsidian-plugins-setup]] for copy-paste setup.
- **Recommended plugins**: Dataview, Breadcrumbs, Obsidian Git, Advanced Tables, Tag Wrangler, Buttons, Graph Analysis, Omnisearch, Templater, Shell commands. Install via `E:\Repos\_scripts\install_obsidian_plugins.ps1` (see [[_ops/obsidian-plugins-setup]]).
- **Syncing with old rig (WORKER-NODE)**: Use Syncthing over SSH. See [[_ops/syncthing-over-ssh-setup]]. Run `E:\Repos\_scripts\syncthing_ssh_tunnel.ps1` to start the tunnel.

## Related
- [[index|Watchers Index]]
- [[../20_projects/Gigatt Transport LLC|Gigatt Transport LLC]]
- [[oldrig]]
- [[newrig]]
