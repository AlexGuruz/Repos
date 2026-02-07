# Remodel Agent Rules (Project-Specific)

## Primary Goal
- Refactor or reorganize safely while preserving behavior.
- Improve maintainability, clarity, and structure without breaking interfaces.

## Non-Negotiables
- No breaking changes to public interfaces without explicit approval.
- No large-scale renames/moves unless requested and justified.
- No dependency changes without documenting why and the tradeoffs.

## Workflow
- Start by mapping the architecture:
  - Key modules
  - Entry points
  - Configuration and runtime assumptions
- When refactoring:
  - Make changes in small, verifiable steps
  - Keep commits atomic and scoped
  - Prefer adapter layers over widespread changes

## Refactor Boundaries
- If asked to refactor a module, do not spill into unrelated folders.
- Avoid formatting-only churn.
- Do not "clean up" code you were not asked to touch.

## Quality Gate
- Ensure:
  - Type checks / linting assumptions remain valid
  - Tests pass or are updated minimally to match unchanged behavior
  - No circular imports introduced
  - Config remains backward compatible

## Output Requirements (Remodel)
- Include:
  - Refactor summary (what moved/changed)
  - Proof of behavior preservation strategy (tests, invariants, before/after notes)
  - Follow-ups (optional improvements) separated from completed work
