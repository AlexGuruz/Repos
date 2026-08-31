# Stage 6 — Always Approve (RESUME)

**Source:** `approval-113` → rule `PAR-A67378BD` (later deleted)  
**Tool:** `cc_investor_demo_ping` · reason `RESUME_ALWAYS_MARKER ping`

| Step | Evidence | Status |
|------|----------|--------|
| Create PAR | `resume_permanent_create.json` | scoped match fields include tool_name + reason |
| Resolve instance | `resume_resolve_always.json` | execute success |
| Matching re-propose | `resume_propose_matching.json` | `approval_required=false`, `auto_permanent=true`, `status=auto_approved` |
| Non-match | `resume_propose_nonmatch.json` | pending `approval-115` |
| Remove rule | DELETE PAR-A67378BD → ok | |
| After remove | propose same reason → `approval-116` pending | matching requires approval again |

Code fix: `operator_desk/approvals.py` now consults `find_matching_rule` and auto-resolves+executes.

Restart process bounce for PAR survival not re-run; on-disk durability + rematch after reload of allowlist file proven via API cycle.

**PASS** (with note on process restart matrix).
