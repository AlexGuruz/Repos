# Repo mirror conventions

## Purpose

Worker (or main) needs a consistent view of repos for the repo cartographer and script librarian.

## Path conventions

- **Main rig (Windows):** Repos live at `E:\Repos\` (or as configured). ai-lab at `E:\Repos\ai-lab`.
- **Worker:** Sync or clone repos under `repos_mirror/` relative to worker's ai-lab root. Example:
  - `repos_mirror/Greg-Kylo/`
  - `repos_mirror/ai-lab/`
  - `repos_mirror/Ai/`

## Sync options

1. **Git on worker:** Clone each repo on worker into `repos_mirror/<name>/`; run `git pull` on a schedule or on-demand.
2. **Sync from main:** Use robocopy (Windows) or rsync (WSL/Linux) from main's E:\\Repos to worker's ai-lab/repos_mirror/.

Cartographer and script librarian use `repos_mirror/` as the root when running on worker; on main they can use `E:\Repos` or `../` relative to ai-lab.

## Handoff rules

- Worker-generated outputs are returned to main over SSH/stdout unless shared storage is explicitly configured.
- Main persists final artifacts in `summaries/` and registry/memory updates as needed.
- Paths used in `registry/scripts.json` must be valid for the execution side (main vs worker) per `docs_source/contracts/worker.md`.
