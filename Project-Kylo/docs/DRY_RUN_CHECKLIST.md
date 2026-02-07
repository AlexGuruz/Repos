## Dry Run Checklist — Unmatched → Approval → Post

Goal: Validate idempotency and unmatched flow with a minimal dataset.

Setup
- Ensure service account has access to: intake workbook (PETTY CASH) and all four target workbooks.
- Confirm `.env` has DATABASE_URL (local) or Docker DSNs as desired.

Steps
1) Ingest two rows into pooled DB from PETTY CASH:
   - Row A: known source with an existing rule
   - Row B: new source with no rule
2) Replicator runs (or manual trigger) and upserts into company DB.
3) Company pipeline runs:
   - Row A → matched and posted (batchUpdate); processed logged; audit written.
   - Row B → suggestion created (not posted); appears in approval queue.
4) Approve a new rule for Row B’s source; publish version N+1.
5) Rerun pipeline for the company:
   - Row B now matches and posts once; no duplicates.

Verify
- No duplicate rows in company DBs (UNIQUE constraints hold).
- posting_batches shows unique idempotency_key per batch.
- processed_transactions updated only after Sheets confirmation.
- Suggestions cleared after approval/post.

Notes
- Replays are idempotent: pool uses ON CONFLICT(signature), replication upserts, posting uses idempotency_key.

