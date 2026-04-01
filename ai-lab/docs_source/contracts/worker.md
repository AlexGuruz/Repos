# Worker contract

Canonical worker identity is maintained in `docs_source/WORKER_CURRENT.md`.

## Worker ↔ main data flow

**Chosen model:** Option 3 — Worker returns results over SSH; main writes to `summaries/` and registry. (Alternative: use shared storage so both see same ai-lab tree; then worker can write directly to shared `summaries/`.)

- Main sends commands to worker via SSH (e.g. `run cartographer for repo X`).
- Worker runs agent code, writes output to temp or stdout.
- Worker returns structured result (e.g. JSON over stdout); main persists to `summaries/repos/<name>.json` and updates project_state if needed.
- If using shared storage (SMB/NFS): worker writes directly to `ai-lab/summaries/`; main reads. Document which in docs_source.

## Path conventions

- **Main rig:** Repos at e.g. `E:\Repos\`; ai-lab at `E:\Repos\ai-lab`.
- **Worker rig:** Clone or sync repos to `repos_mirror/` under worker's ai-lab (or shared path). Example: `repos_mirror/Greg-Kylo/`, `repos_mirror/ai-lab/`. Cartographer and script librarian use `repos_mirror/` as root on worker.

## Handoff authority

- Worker performs compute/scan tasks and returns structured output.
- Main is the persistence authority for `summaries/`, registry updates, and policy-governed state mutations.
- Any exception to this (shared writable storage) must be documented before enabling worker direct writes.

## Health

- A **privileged collector** (script or service, not an agent) runs with sufficient privileges and writes:
  - `observability/health.json` — SSH reachable, disk, key processes, Ollama/service status.
  - Optionally `observability/security.json`, `observability/services.json`.
- **Agents never write** these files; they **only read** for observability.

## Secrets

- Scripts that need API keys (e.g. GrowFlow) run on **main** where env/secrets are available, or main passes env over SSH for that run only (e.g. inject into remote command env). Worker does not have persistent access to secret store.
- Registry and contracts reference auth by **env var name** only (e.g. `GROWFLOW_API_KEY`); no secrets in repo.
