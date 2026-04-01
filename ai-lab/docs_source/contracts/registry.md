# Registry contract

Registry is the executable catalog used by orchestration and execution layers.

## File: `registry/scripts.json`

Array of script/tool entries. Schema per entry:

| Field    | Type   | Description                                      |
|----------|--------|--------------------------------------------------|
| tool_name| string | Unique id (e.g. `growflow_sales_today`)          |
| path     | string | Path to script (main rig or worker-relative)      |
| purpose  | string | One-line description                             |
| inputs   | array  | Parameter names (e.g. `["date", "location_id"]`) |
| outputs  | array  | Output keys (e.g. `["gross_sales", "order_count"]`) |
| auth     | string | Env var name only (e.g. `GROWFLOW_API_KEY`); no secrets |
| status   | string | e.g. `working`, `experimental`, `deprecated`      |

## Path convention

- **Main rig (Windows):** Absolute or relative to ai-lab root, e.g. `E:\Repos\Greg-Kylo\scripts\foo.py` or `../Greg-Kylo/scripts/foo.py`.
- **Worker rig:** Relative to worker's ai-lab or repos_mirror, e.g. `repos_mirror/Greg-Kylo/scripts/foo.py`. Document worker root in `docs_source/contracts/worker.md`.

## Other registry files (skeleton)

- `registry/repos.json` — repo list, paths, last_scan
- `registry/integrations.json` — external integrations (GrowFlow, Sheets, etc.)
- `registry/workflows.json` — known workflow ids and descriptions
- `registry/services.json` — services and health source refs

Implement scripts.json first; others can be `[]` or `{}`.

## Handoff notes

- `path` values must be execution-context aware (main vs worker) and stay consistent with `docs_source/contracts/worker.md`.
- `auth` stores env var names only; secrets never belong in registry entries.
