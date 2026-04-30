# Repo Documentation Maintainer

## Purpose

Provide a governed documentation-maintenance assistant role that:

- inspects existing repo documentation freshness from prepared context (`repo_pulse`),
- returns a prioritized docs cleanup plan,
- drafts approval-gated documentation update proposals.

This role does **not** directly edit files.

## Supported prompts

- Status:
  - `what docs need cleanup?`
  - `which repos have stale docs?`
  - `explain repo documentation status`
  - `which README needs updating?`
  - `validate repo documentation`
  - `what sections are missing in docs?`
  - `what is wrong with this README?`
- Planning:
  - `make a docs cleanup plan`
  - `plan documentation updates for ai-lab`
  - `what should the docs maintainer update first?`
- Proposal:
  - `draft updates for README`
  - `prepare a docs update proposal`
  - `propose updates for stale repo docs`
  - `improve this repo documentation`

## Data sources

Primary:

- `state/prepared_context/repo_pulse.json`

Secondary:

- `state/prepared_context/system_snapshot.json` (freshness/system role context)

No worker calls are required for normal status/plan/proposal turns.

## Policy and validation (Phase 7)

Canonical policy description: [`REPO_DOCUMENTATION_POLICY.md`](REPO_DOCUMENTATION_POLICY.md).

Behavior:

- **Deterministic checks** in `brain/repo_doc_policy.py` + `brain/repo_doc_validation.py` (no LLM).
- **Status** attaches `readme_validations` per repo and optional `aux_doc_validation` (bounded runbook/system-map samples).
- **Findings** may include `readme_validation` (full result dict) when a README was checked.
- **Cleanup plan** items include `readme_validation`, `priority_score` (missing required sections weighted highest).
- **Proposals** include `issues`, `missing_sections`, `weak_sections`, `proposed_sections` (outline + policy reasoning), and `approval_required: true`.

Reference templates (never auto-applied): `docs/templates/README_TEMPLATE.md`, `docs/templates/RUNBOOK_TEMPLATE.md`.

## Approval behavior

- Proposals that imply file edits are marked `approval_required: true`.
- Action class is `modifies-files-or-state`.
- For docs proposal prompts, the orchestrator creates an approval queue entry (`approval-...`) with an approval-compatible payload.
- No file changes are applied automatically.
- No auto-commit behavior is added.

## Examples

### Status

Returns:

- snapshot freshness (`generated_at`, `stale`),
- confidence,
- source paths,
- findings with risk and approval requirement.

### Cleanup plan

Returns prioritized items with:

- repo,
- doc file,
- issue found,
- recommended update,
- risk level,
- approval required,
- suggested verification.

### Update proposal

Returns:

- target file,
- reason,
- proposed change summary,
- before/after outline,
- patch preview,
- verification steps,
- approval request id.

## Limitations

- It relies on prepared context and may be limited when `repo_pulse` is missing or stale.
- It does not run deep live scans unless explicitly requested by separate flows.
- It drafts proposals but does not execute file edits.

## Verification steps

1. Run status: `what docs need cleanup?`
2. Run plan: `make a docs cleanup plan`
3. Run proposal: `prepare a docs update proposal`
4. Confirm:
   - output includes freshness/confidence/source paths,
   - proposal shows `approval_required: true`,
   - no files changed directly from chat action.

## Future expansion

- Add repo-scoped optional deep inspection mode (explicit user request only).
- Deeper runbook/system-map coverage with explicit path hints from users.
- Add command-center summary view if needed (read-only).

