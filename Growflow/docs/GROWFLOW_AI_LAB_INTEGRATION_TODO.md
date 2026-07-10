# Growflow AI-Lab Integration TODO

This workspace has direct access to `ai-lab`, so baseline integration is implemented in:

- `ai-lab/brain/prepared_context/builders.py` (growflow snapshot enrichment)
- `ai-lab/command-center/command-center/backend/routers/prepared_context.py` (`/api/growflow/validation-status`)

If additional rollout is needed, use this checklist:

1. schedule `Growflow/scripts/*` canonical runners in strict mode.
2. ensure report directories are readable by ai-lab process.
3. expose latest validation status in Growflow panel/tool cards:
   - metric id
   - latest validation timestamp
   - ok/confidence
   - warning/error reason
4. set panel color mapping:
   - green: `ok=true` and no warnings
   - yellow: `ok=true` with warnings
   - red: `ok=false`
5. block prepared-context "healthy" state when latest report for any required metric is failed.
