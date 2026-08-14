# Repository path migration

**Effective:** July 2026  
**Workspace root:** `E:\Repos`  
**Status:** Acheron source layout migrated; external runtime verification remains separate.

## Why this note exists

The workspace moved from many flat, inconsistently named folders into status-based zones. Older chats, generated Obsidian notes, historical evidence, and some runbooks may still display former paths. Agents must distinguish historical references from executable instructions.

## Canonical mapping

| Retired path | Current path |
|---|---|
| `E:\Repos\Project-Kylo` | `E:\Repos\products\project-kylo` |
| `E:\Repos\Greg-Kylo` | `E:\Repos\products\greg-kylo` |
| `E:\Repos\Growflow` | `E:\Repos\products\growflow` |
| `E:\Repos\cog-allocation-system` | `E:\Repos\products\cog-allocation` |
| `E:\Repos\ai-lab` | `E:\Repos\products\ai-lab` |
| `E:\Repos\ai-lab-governance` | `E:\Repos\products\ai-lab-governance` |
| `E:\Repos\kylo-site` | `E:\Repos\products\kylo-site` |
| `E:\Repos\geomapper app` | `E:\Repos\products\gigatt-geomapper` |
| `E:\Repos\Ai` | `E:\Repos\internal\obsidian-brain` |
| `E:\Repos\Gigatt Transport LLC` | `E:\Repos\internal\gigatt-transport` |
| `E:\Repos\Home` | `E:\Repos\internal\home` |
| `E:\Repos\PilotCarMap` | `E:\Repos\archive\pilot-car-map` |
| `E:\Repos\PettyCash_Migration_Package` | `E:\Repos\archive\pettycash-migration` |
| `E:\Repos\activepieces` | `E:\Repos\vendor\activepieces` |
| `E:\Repos\BMAD-METHOD` | `E:\Repos\vendor\bmad-method` |
| `E:\Repos\awesome-n8n-templates` | `E:\Repos\vendor\awesome-n8n-templates` |

The complete machine-readable mapping is in `tools/migration/layout.json`.

## Runtime paths

The source-tree migration does not automatically prove that remote services are healthy.

- Acheron source: `E:\Repos\products\project-kylo`
- power-1 mirror: `C:\worker\repos\products\project-kylo`
- power-1 compatibility alias: `C:\Project-Kylo`
- power-1 Greg mirror: `C:\worker\repos\products\greg-kylo`

`C:\Project-Kylo` may remain in operational scripts when it intentionally refers to the compatibility junction. An `E:\Repos\Project-Kylo` reference is stale unless it is clearly marked as historical evidence.

## Required agent workflow

1. Open `E:\Repos\Repos.code-workspace`.
2. Read root `AGENTS.md`.
3. Resolve products through:
   - Python: `tools/migration/python/repos_paths.py`
   - PowerShell: `tools/migration/lib/Paths.psm1`
4. Before editing automation, search for retired absolute paths.
5. Run local verification after path-related changes.
6. Treat power-1 sync, junction changes, task reinstall, and watcher recreation as explicit operational steps.

## Local verification

```powershell
cd E:\Repos\tools\migration
python -m pytest python\test_repos_paths.py -q
.\verify.ps1
```

## Post-migration verification status

Recorded August 2026 after the hard cut. Re-verify before trusting these numbers.

| Product | Command | Result |
|---|---|---|
| Path helpers | `python -m pytest tools\migration\python\test_repos_paths.py -q` | 6 passed |
| Growflow | `python -m pytest -q tests` | 170 passed |
| Project Kylo | `python -m pytest -q --noconftest scaffold\tests\{posting,audit,intake}` | 72 passed |
| Governance | `python bootstrap\verify_governance.py`, `python scripts\verify_catalog.py` | both OK |
| Geomapper | `python -m pytest -q tests` | 7 skipped (needs live server + Supabase) |
| AI Lab | `python -m pytest -q -s tests` | 355 collected, 6 genuine failures (all config/snapshot drift, none path-related) |
| Greg Kylo | `python -m pytest -q -m "not integration"` | pre-existing rebrand drift, see below |

No failure in any suite was caused by an unresolved path. Every product resolves its own root correctly after the move.

### Run AI Lab tests with `-s`

Several AI Lab tests shell out to `git` and hardware probes. Under pytest's default output capture, launched from inside a piped shell command, Windows handle duplication fails and roughly 15 tests fail with `OSError: [WinError 6] The handle is invalid`. They all pass with capture disabled:

```powershell
cd E:\Repos\products\ai-lab
python -m pytest -q -s tests
```

Treat any `WinError 6` in this suite as an invocation artifact, not a real defect.

### Two migration gotchas worth remembering

**Stale bytecode caches.** Moving directories preserves file mtimes, so cached `.pyc` files stay valid and keep the *old* absolute path in their embedded `co_filename`. Tracebacks then point at paths that no longer exist and pytest prints `???` instead of source lines. If you see a traceback citing a retired path, purge caches before believing it:

```powershell
Get-ChildItem E:\Repos\products -Recurse -Force -Directory -Filter __pycache__ |
  Where-Object { $_.FullName -notmatch '\\\.venv\\|\\node_modules\\|\\site-packages\\' } |
  Remove-Item -Recurse -Force
```

**`agents` package name collision (ai-lab).** The installed `openai-agents` SDK also publishes a top-level `agents` module. A namespace directory (no `__init__.py`) loses to it during import resolution, which silently breaks `from agents.repo_cartographer...` and `from agents.feedback_interpreter...` in the orchestrator. `products\ai-lab\agents\__init__.py` must exist to keep the first-party package winning.

### Pre-existing issues, not caused by the move

- **Greg Kylo rebrand drift.** Commit `6259a51` renamed the triage entry point `triage_company_batch` to `triage_account_batch` and moved to account-based tables, but parts of the test suite still assume the company-based schema. Three files fail to import and roughly a dozen assertions expect the old shape. This needs a product decision, not a path fix.
- **AI Lab worker URL tests.** `ops\registry\workers.yaml` defines a secondary tunnel on `:8766`, so URL resolution returns the secondary entry while the March-era tests still assert the primary `:8765`. Infrastructure config outran the tests.
- **AI Lab committed inventory snapshots are stale.** `test_growflow_canonical_runners` and `test_integration_inventory_generator` compare a committed snapshot generated 2026-04-28 against a live rescan (71 vs 96 scripts, 222 vs 376 entries). They need regeneration, which is a separate maintenance chore.

## Outstanding operational work

Not done, and each needs an explicit decision:

1. **Scheduled tasks point at retired paths.** 18 Windows tasks still invoke `E:\Repos\Growflow\scripts\...` and `E:\Repos\ai-lab\scripts\...`, which no longer exist, so every one of them fails silently at its next trigger. Reinstall with `tools\migration\tasks_reinstall.ps1 -Apply` after reviewing the dry run. (Not in scope for the Aug 2026 husk/topology pass.)
2. **power-1 mirror.** Junction, sync, smoke test, and task reinstall on the worker rig remain untouched.
3. **The root `E:\Repos` working tree is enormous and uncommitted.** See topology decision below before any large commit.

## Project-Kylo husk recreation (resolved Aug 2026)

**Symptom:** empty `E:\Repos\Project-Kylo\.secrets` (zero files) made `verify.ps1` fail `legacy gone Project-Kylo`.

**What was recreating it:** No live scheduled task targets `E:\Repos\Project-Kylo`. Closest residual creators / pointers found and fixed:

| Source | Risk | Fix applied |
|---|---|---|
| `products/project-kylo/tools/debug/*.py` + `scripts/run_raw_clean.py` | Hardcoded `E:\Repos\Project-Kylo` reads/writes could recreate the retired root if run | Rewrote to `E:\Repos\products\project-kylo` |
| Obsidian note `20_projects/Project-Kylo/.secrets.md` | Frontmatter `repo_path: E:\Repos\Project-Kylo\.secrets` (stale map of the secrets folder) | Pointed at `products/project-kylo/.secrets` |
| `tools/scripts/_scripts/repo_obsidian_map.json` | Did not ignore `.secrets` subfolders when noting repos | Added `.secrets` to default `ignore_patterns` |
| `tools/scripts/root-scripts/drive_folder_download.py` | Error text still said `Project-Kylo/.secrets` (path already zoned) | Message updated |
| `docs/SYSTEMS_AND_REPOS.md` | Documented flat `.secrets` paths | Updated to zoned paths |

Intermittent recreation was also observed after husk moves (empty `.secrets` only, no matching scheduled task). Idle + isolated `git status` did not recreate it; a subsequent clear immediately before `verify.ps1` stayed clean for the full verify run. Empty husks were moved under `archive\_empty-husk-*` / `archive\_empty-project-kylo-husk-*` (not deleted when credential files might appear). Canonical secrets remain at `products/project-kylo/.secrets` and/or `E:\secrets`. If the stub returns, move it again only when file-count is zero and re-run verify.

**Empty `.git` repair status:** Completed. Removed the empty `products/project-kylo\.git` directory marker and attached a real gitdir from `AlexGuruz/Project-Kylo` (HEAD `8b52a843ebb15637ed16f31898a0999bee7ab234` on `main`, remote `origin` → `https://github.com/AlexGuruz/Project-Kylo.git`) without checkout/reset --hard. Ran `git reset` (mixed) so the index matches HEAD while leaving the working tree intact. Expect many local `D`/`M` vs `origin/main` — that is local drift, not a failed attach. On this volume git may need `git -c safe.directory=E:/Repos/products/project-kylo …` rather than a global `safe.directory` config change.

## Git topology decision: **(B) sibling / nested clones**

**Decision:** Prefer **(B)** — keep nested-git products as real clones of their own remotes under `products/`. Do **not** land Project Kylo (or other nested_git trees) as one huge commit into `AlexGuruz/Repos`.

**Rationale:**

- `layout.json` already marks `project-kylo`, `greg-kylo`, `kylo-site`, and `gigatt-geomapper` as `nested_git: true`.
- Those four already have healthy separate GitHub remotes (`AlexGuruz/Project-Kylo`, `Greg-Kylo`, `kylo-site`, `gigatt-geomapper`).
- Growflow / AI Lab / COG / governance historically live in the monorepo and have no standalone AlexGuruz product remotes.
- power-1 expects `C:\worker\repos\products\project-kylo` as a real checkout (plus `C:\Project-Kylo` junction), which matches nested clones, not a monorepo-only blob.
- An empty `.git` under `products/project-kylo` previously made tools walk up into `E:\Repos` git — now repaired.
- A massive (A)-style commit of `products/**` into `AlexGuruz/Repos` would fight existing remotes, risk secret leakage in the staged set, and worsen editor `git diff` load.

### Human next steps (no push; no force)

1. **Optional monorepo settle later:** on `AlexGuruz/Repos`, commit zone scaffolding + non-nested products (`growflow`, `ai-lab`, `cog-allocation`, `tools`, `docs`, …) only after a staged-set secret scan. Keep nested_git product trees out of that commit (gitignore or leave untracked). Do not push until reviewed. This pass intentionally did **not** create that commit.
2. **Reconcile project-kylo local drift** against `origin/main` / feature branches carefully — never `reset --hard` without an explicit backup of local work.
3. **power-1:** sync `products/project-kylo` mirror, verify junction, smoke — separate ops change.
4. **Scheduled tasks:** still need `tasks_reinstall.ps1 -Apply` when explicitly requested.
5. **If `E:\Repos\Project-Kylo` stub returns:** confirm zero files, move to `archive\_empty-husk-*`, re-run `tools\migration\verify.ps1`.

## Obsidian map remap

**2026-08-06:** Remapped `tools/scripts/_scripts/repo_obsidian_map.json` with `tools/migration/obsidian_remap.ps1 -Apply` (dry-run first). Vault and mapped `repo_path` entries now use zoned paths (`internal\obsidian-brain\Obsidian\Brain`, `products\...`, etc.). The remapper was updated to rewrite JSON-escaped (`\\`) path strings as well as literal ones. `connect_brain_vault.ps1` already defaults to the zoned vault.

### Vault frontmatter remap (2026-08-13)

Ran `tools/migration/obsidian_frontmatter_remap.ps1` (dry-run, then `-Apply`) against the canonical vault `internal\obsidian-brain\Obsidian\Brain` only. Duplicate under `products\ai-lab\Ai\Obsidian\Brain` was left alone (connect scripts already point at the canonical vault).

| Metric | Count |
|---|---|
| Notes scanned | 521 |
| Notes with remappable flat `repo_path` | 472 |
| Notes written | 472 |
| Remaining flat `repo_path` (no layout mapping) | 1 (`E:\Repos\Worker\...`) |
| Body `**Repo path:**` leftovers (same mapping; not rewritten) | ~305 |
| Backup | `tools/migration/reports/vault-frontmatter-backup.20260813-133537` (472 files) |

Top remapped prefixes: Project-Kylo 130, ai-lab 120, Greg-Kylo 117, Growflow 31, Gigatt Transport LLC 28, PettyCash 21, ai-lab-governance 16, cog-allocation-system 9.

Optional follow-up: `-IncludeBody` on the same script to rewrite note-body path displays that mirror frontmatter.

## Executable stale-path sweep (2026-08-13)

Scanned `products\`, `tools\`, `internal\` for retired absolute paths in `*.ps1` / `*.py` / `*.bat` / `*.cmd` / `.env*` / `*.yaml` / `*.yml` / `*.json`, skipping `node_modules`, `.venv`, `openai-agents-python`, archive/vendor, migration reports, and `.claude\worktrees`.

| Bucket | Result |
|---|---|
| High-confidence operational fixes applied | 3 files (`clear_locks.ps1` guidance; governance allowlist/repo_classes comment examples) |
| Executable surfaces already zoned | Prior rewrite pass left registries, task installers, ops scripts, and product defaults clean |
| Deferred — docs / evidence / runbooks | ~37 unique files under `docs\` + product `docs\` (including evidence `.ps1` under ai-lab docs) |
| Deferred — archive | ~100+ unique files (historical) |
| Deferred — vault note bodies | ~305 `**Repo path:**` lines still flat |
| Deferred — `.claude\worktrees` copies | stale `Ai\Obsidian\Brain` defaults in growflow worktree `_scripts` (skipped by policy) |
| Deferred — scheduled tasks on disk | Still need explicit `tasks_reinstall.ps1 -Apply` (see Outstanding operational work) |

Did **not**: commit/push, reinstall scheduled tasks, touch power-1, or delete secrets.

## Known historical-reference areas

These may contain old paths without indicating current breakage:

- archived migration documents
- committed test evidence and captured pytest output
- generated Obsidian project-history note **bodies** (frontmatter `repo_path` remapped 2026-08-13)
- old chat recovery inventories
- `.claude\worktrees` snapshots

Executable scripts, `.env` files, registries, Cursor rules, task installers, and current runbooks must use the canonical mapping.
