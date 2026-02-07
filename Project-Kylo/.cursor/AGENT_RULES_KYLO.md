# Kylo Agent Rules (Project-Specific)

## Primary Goal
- Maintain correctness of financial automation and data routing.
- Preserve existing workflows unless explicitly changing them.

## Non-Negotiables
- No schema changes without explicit approval and a migration plan.
- No silent behavior changes in calculations, mappings, or routing logic.
- No changes to integration boundaries (Sheets, DB, Kafka/Redpanda, APIs) without documenting impact.

## Workflow
- Identify the entry point(s) for the requested change:
  - API service entry (e.g., FastAPI app)
  - Worker/consumer entry (e.g., Kafka consumer)
  - Scheduler/cron entry
  - Apps Script / Sheets integration points
- Trace the data flow end-to-end before editing:
  - Input source -> parsing/validation -> transformation -> persistence -> outbound events

## Safety Checks Before PR/Commit
- Confirm environment variables/config keys involved
- Confirm topic names / routing keys / event schemas impacted
- Confirm DB schema/table dependencies if any
- Confirm idempotency and retry behavior for workers/consumers

## Coding Preferences
- Pydantic models: keep strict validation and explicit types
- Logging: structured, minimal, and useful (no spam)
- Errors: fail fast with explicit messages; avoid broad exception catches
- Tests: if change affects routing or calculations, add/adjust tests

## Output Requirements (Kylo)
- Include:
  - What changed (behavior-level)
  - What did NOT change (explicitly)
  - Integration impact checklist (Sheets/DB/Kafka/APIs)
  - Any migrations needed (usually none unless approved)
