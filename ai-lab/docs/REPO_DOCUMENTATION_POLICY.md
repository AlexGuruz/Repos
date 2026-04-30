# Repo documentation policy

This document defines **what good documentation looks like** for repositories covered by the repo documentation maintainer. Validation is **deterministic** (pattern and structure checks only, no LLM).

## README requirements

Required sections (heading text must match one of the listed patterns, case-insensitive):

| Section | Typical headings |
|--------|------------------|
| Overview | Overview, Introduction, About, Purpose |
| Setup | Setup, Installation, Getting started, Quick start |
| Configuration | Configuration, Environment, Env vars, Variables, `.env` |
| Usage | Usage, Running, How to run, Entrypoint, Commands |
| Architecture | Architecture, System overview, Design, How it works |
| Verification | Verification, Testing, How to confirm, Validate, Check that |

Optional: troubleshooting, roadmap, dependencies.

Rules:

- Sections must not be effectively empty (substantive body under each matched heading).
- Placeholder phrases (TODO, TBD, lorem, “coming soon”, etc.) in section bodies are flagged.
- At least one **actionable** line is required document-wide (e.g. fenced code block or a recognizable install/run command).

Good vs bad:

- **Good**: Each required heading exists with 2+ sentences or bullets; includes fenced commands for install and verify.
- **Bad**: Only a title and a one-line description; “Setup: TBD”; no commands or code fences anywhere.

## Runbook requirements

Required:

- **Purpose** — why the runbook exists.
- **Steps** — ordered procedure with concrete actions/commands where possible.
- **Expected result** — how to know the run succeeded.
- **Failure handling** — what to do when something goes wrong.

Optional: prerequisites.

Same non-empty and anti-placeholder rules apply where configured.

## System map requirements

Required:

- **System components** — services, modules, or major parts.
- **Data flow or relationships** — how information moves or how pieces relate.
- **Integration points** — external systems, APIs, queues, etc.

Optional: ownership / contacts.

System maps are **not** required to include shell commands; actionable-step rules are relaxed for this doc type in code.

## How the maintainer uses policy

1. **Status** (`analyze_repo_docs_status`): loads `repo_pulse`, then for each repo with `readme_present` runs `validate_readme` on `README.md`. Bounded glob discovery may attach runbook/system-map validation samples under `aux_doc_validation`.
2. **Cleanup plan** (`build_docs_cleanup_plan`): sorts plan items by `priority_score` (missing required README sections, weak sections, risk).
3. **Proposal** (`create_docs_update_proposal`): builds `issues`, `missing_sections`, `weak_sections`, and `proposed_sections` (name, outline, optional example text, policy reasoning). **No files are written.**

Templates for human reference only (not auto-applied): `docs/templates/README_TEMPLATE.md`, `docs/templates/RUNBOOK_TEMPLATE.md`.

## How proposals are generated

Proposals are **approval-gated** (`approval_required: true`, `write_docs_update`). They summarize the top plan item and attach structured `proposed_sections` derived from policy keys that failed validation. Execution of edits remains outside this module.

## Benchmarks (local)

Orchestrator prompts can be exercised with `scripts/benchmark_ai_response.py` (stdout only by default; set `AI_LAB_BENCH_WRITE_DOC=1` to refresh `docs/AI_RESPONSE_BENCHMARKS.md` for committed snapshots). Optional env `AI_LAB_DOC_BENCH=1` prints direct timings for `validate_readme`, `build_docs_cleanup_plan`, and `create_docs_update_proposal` (no worker, no LLM).

Targets (typical dev machine, ai-lab-sized tree):

- README validation (single file): under **300 ms**
- Cleanup plan: under **1 s**
- Proposal: under **2 s**

Actual times depend on repo count and filesystem; CI may set thresholds separately.
