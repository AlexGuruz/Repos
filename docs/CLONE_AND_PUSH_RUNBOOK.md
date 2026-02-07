# Repos: Clone and Push Runbook

Runbook for pushing this monorepo to GitHub (new rig) and cloning on the old rig. Repos is the parent folder; it contains projects, `Ai/` (Obsidian vault), and `Worker/`.

---

## First push (new rig)

1. **Create a new GitHub repo** (e.g. `Repos` or `workspace`)
   - Do not initialize with README (we have existing content).

2. **Repo size check** (before first push)
   - Run `git add .` then inspect (e.g. `git status`). If the repo is very large (PettyCash, Exzact PDFs/PPTX, etc.), add more exclusions to `.gitignore` so the repo stays under ~5GB (GitHub recommendation).

3. **Add remote and push**
   ```powershell
   cd E:\Repos
   git remote add origin https://github.com/<user>/<repo>.git
   git add .
   git commit -m "Initial: Repos parent with Ai, Worker"
   git branch -M main
   git push -u origin main
   ```

---

## Clone on old rig

1. **If E:\Repos (or C:\Repos) already exists with content**
   - Back it up, delete or rename it, then clone; or clone into a temp path and merge manually. `git clone` into an existing non-empty directory will fail.

2. **Clone**
   ```powershell
   # Clone to E:\Repos (or C:\Repos if old rig uses C:)
   git clone https://github.com/<user>/<repo>.git E:\Repos
   ```

3. **Post-clone**
   - **Obsidian**: Open Obsidian and add vault: `E:\Repos\Ai\Obsidian\Brain`
   - **Plugins** (optional): Run `E:\Repos\_scripts\install_obsidian_plugins.ps1` (plugins may already be in repo)
   - **Sync**: Run `E:\Repos\_scripts\repo_obsidian_sync.ps1 -RunOnce` if needed
   - **Secrets**: E:\secrets and per-repo `.secrets` are not in the repo. Set up credentials on old rig: copy from new rig or follow [MISSING_FROM_REPOS.md](MISSING_FROM_REPOS.md) (Google service account, Kylo .secrets, PettyCash config, etc.)
   - **Worker**: Old rig has C:\worker (supervisor, watchdog, agents). Repos\Worker is empty after clone. Either keep C:\worker as runtime and use Repos\Worker for syncable config only, or copy C:\worker content into Repos\Worker on new rig and push so both rigs share the same Worker tree
   - **Syncthing**: Set up Syncthing (Send Only / Receive Only as desired) for ongoing sync

---

## Path reference

| Before                 | After                        |
| ---------------------- | ---------------------------- |
| `E:\Ai\Obsidian\Brain` | `E:\Repos\Ai\Obsidian\Brain` |
| `E:\Worker`            | `E:\Repos\Worker`            |
| `repos_root`           | `E:\Repos` (unchanged)       |

If the old rig uses C: instead of E:, clone to `C:\Repos` and update `_scripts/repo_obsidian_map.json` on that machine if needed (e.g. `vault_path`, `repos_root`, and `repo_path` in mappings).
