# Documentation Standard

This file defines the uniform documentation standard for active `ai-lab` system docs.

## Scope

Active system docs are:

- `README.md`
- `docs_source/*.md`
- `docs_source/contracts/*.md`
- `command-center/command-center/*.md`
- `m6b-docsync/m6b-docsync/*.md` and child docs

Archived/reference mirrors (for example `Ai/Obsidian/...`) are not treated as authoritative runtime docs.

## Source-of-truth order

When docs disagree, resolve in this order:

1. Runtime code/config (`brain/`, `command-center/.../backend/core/config.py`, `policy/`, `registry/`, `memory/`)
2. `docs_source/WORKER_CURRENT.md` (worker identity and host constants)
3. `docs_source/contracts/*.md` (interface/handoff contracts)
4. Feature-level docs (`command-center/.../README.md`, `m6b-docsync/...`)
5. Narrative/planning docs (`Guru.md`)

## Required consistency rules

- Worker identity must be consistent across docs (`worker@worker-node`, `worker-node`, `http://worker-node:11434`) unless explicitly marked legacy.
- Paths in examples must match current repo layout (for command center: `ai-lab/command-center/command-center`).
- Any policy/autonomy claim must align with `policy/autonomy_policy.yaml`.
- Any execution/logging claim must align with `brain/execution.py`.
- Any config key examples must align with current app settings names.

## Handoff rule

- Worker performs execution/scanning and returns structured output.
- Main persists authoritative state (`summaries/`, `registry/`, `memory/`, policy-governed updates).
- Deviations (for example shared writable storage) must be documented in `docs_source/contracts/worker.md` first.

## Update protocol

1. Update source-of-truth runtime/config first.
2. Update `docs_source/WORKER_CURRENT.md` if worker identity changes.
3. Update affected contract doc(s) under `docs_source/contracts/`.
4. Update feature docs (`README.md`, command center docs, DocSync docs).
5. Run a consistency sweep before merge.
