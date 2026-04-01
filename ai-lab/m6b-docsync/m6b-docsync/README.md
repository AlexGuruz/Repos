# M6B · DocSync — Stale Detection & Proposal Engine

This package defines the complete rules, schemas, and templates for the M6B
milestone: detecting stale documentation and delivering structured proposals
to the command center UI (Capacitor app on phone).

Repository-wide documentation consistency rules live in `../../docs_source/DOCUMENTATION_STANDARD.md`.

---

## File index

```
m6b-docsync/
├── rules/
│   ├── STALENESS_RULES.md      — what "stale" means, all 4 trigger types,
│   │                             drift scoring, exemptions, scan cadence
│   └── AGENT_RULES.md          — DocSync agent system prompt / behavioural
│                                  rules (paste into agent config)
├── schemas/
│   ├── PROPOSAL_SCHEMA.json    — JSON Schema for every proposal object
│   └── DECISION_LOG_SCHEMA.json— JSON Schema for append-only decision log
└── templates/
    ├── PROPOSAL_CARDS.md       — exact card formats for command center chat
    │                             (all triggers + edge cases)
    └── EXAMPLE_PROPOSALS.json  — 4 fully-populated example proposal objects
                                   (one per trigger, covering all statuses)
```

---

## How the pieces connect

```
Git push / cron / manual scan
        │
        ▼
  DocSync agent (worker-7b)
        │  reads STALENESS_RULES.md
        │  applies AGENT_RULES.md
        │
        ├─ trigger fires
        │      │
        │      ▼
        │   Build proposal object
        │   (validated against PROPOSAL_SCHEMA.json)
        │      │
        │      ▼
        │   POST /api/docsync/proposals
        │      │
        │      ▼
        │   EventBus → WebSocket → Command Center UI
        │      │
        │      ▼
        │   Card rendered in chat (PROPOSAL_CARDS.md format)
        │      │
        │      ▼
        │   SG taps [Approve / Reject / Defer] on phone
        │      │
        │      ▼
        │   Decision written to decision_log.jsonl
        │   (validated against DECISION_LOG_SCHEMA.json)
        │      │
        │      ▼
        │   If approved → doc update applied, commit SHA recorded
        │
        └─ no triggers → clean scan card emitted
```

---

## Trigger quick reference

| ID | What fires it | Severity | Auto-propose |
|---|---|---|---|
| T1 | Symbol added or removed | INFO / WARN | Yes |
| T2 | Function signature changed | WARN | Yes |
| T3 | File moved or renamed | WARN | Yes |
| T4 | Config key added/removed/renamed | INFO / CRITICAL | Yes |

---

## Drift score thresholds

| Score | UI appearance |
|---|---|
| ≥ 6 | CRITICAL badge · top of sidebar |
| 3 – 5 | WARN badge |
| < 3 | INFO badge |

Escalation fires at **7 days** with no decision, regardless of score.

---

## Decision log location

Append to: `{AI_LAB_GOVERNANCE_ROOT}/docsync/decision_log.jsonl`

One JSON object per line. Never delete entries. Schema:
`schemas/DECISION_LOG_SCHEMA.json`

---

## Next steps after M6B

| Milestone | Scope |
|---|---|
| M7 | Wire actual tree-sitter AST diff into DocSync agent |
| M7 | Implement `/api/docsync/proposals` endpoint in command center backend |
| M7 | Render proposal cards as first-class UI component in ChatPanel.jsx |
| M8 | Semantic drift detection (LLM eval pass: does the doc *mean* what the code *does*?) |
| M9 | Third-party dependency changelog tracking |
| M10 | Capacitor app packaging and phone deployment |
