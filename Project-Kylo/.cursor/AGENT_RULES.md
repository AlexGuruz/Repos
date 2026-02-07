# Global Agent Rules (Applies to all work)

## Communication
- No emojis
- No conversational filler
- No opinions
- No speculation presented as fact
- Be direct, technical, and concise
- Prefer headings, bullet points, and short tables

## Repo Discipline
- Read repo structure before changes (list key directories and entry points)
- Identify and respect existing conventions (naming, layout, patterns)
- Do not invent dependencies, APIs, or file paths
- Do not change unrelated code
- If requirements are unclear, stop and state what is unknown

## Code Change Rules
- Prefer minimal, reversible changes
- Avoid sweeping refactors unless explicitly requested
- Do not delete code without a stated reason and impact summary
- Do not rewrite formatting across the repo unless asked
- Keep comments minimal and useful (no commentary)

## Output Requirements
- Provide a clear change summary
- List files changed
- When helpful, show diffs or pseudodiffs
- Call out risks and follow-ups explicitly

---

## GitHub Actions Discipline

### Gating Policy
- Agents do not merge "green-ish" — agents merge **green**.
- All required checks must pass before requesting review or merge.

### Required Checks (Minimum)
| Check | Priority |
|-------|----------|
| Lint | Required (fast) |
| Unit tests | Required (fast) |
| Type checks | Required (if applicable) |
| Integration tests | Recommended |
| Build/package | Required (if relevant) |

### Agent CI Workflow
1. Create branch (see Branch Naming below)
2. Push changes
3. Run/check CI
4. Fix until **all checks green**
5. Only then request review/merge

### CI Summary Comment Format (Required in PR)
Agents must include this block in every PR description:

```
## CI Status
- Checks passed: <list>
- Checks failing: <list> (with next action if any)

## Risk
<low|med|high> — <reason>

## Files Changed
<grouped list>
```

---

## Branch + Commit Strategy

### Branch Naming (Strict)
Use one of:
- `agent/audit/<topic>`
- `agent/refactor/<topic>`
- `agent/bugfix/<topic>`
- `agent/feature/<topic>`
- `hotfix/<topic>` (human only)

Examples:
- `agent/refactor/event-dispatcher-idempotency`
- `agent/bugfix/kafka-consumer-retry-loop`

### Commit Message Format (Strict)
```
<type>(<scope>): <imperative summary>
```

Types: `audit`, `refactor`, `fix`, `feat`, `chore`, `docs`, `test`

Examples:
- `fix(consumer): prevent duplicate processing on retry`
- `refactor(router): extract topic mapping table`
- `test(events): add idempotency regression coverage`

### Commit Discipline
- 1 commit = 1 logical change
- No "cleanup" commits mixed into logic changes
- No repo-wide formatting changes

### PR Policy
- PR title matches the primary commit message
- PR description must include:
  - What changed
  - What did NOT change
  - CI status (see format above)
  - Integration impact (Kylo: Sheets/DB/Kafka/APIs)
