# Operator Desk HTTP API

Mounted by Command Center only when `OPERATOR_DESK_ENABLED=1` (Gate 4 Integration).

| Method | Path | Purpose |
|--------|------|---------|
| GET | /api/operator/health | Liveness |
| GET | /api/operator/jobs | List job_ids |
| GET | /api/operator/jobs/{job_id} | Primer bundle |
| GET | /api/operator/growflow/status | Snapshot/API status |
| GET | /api/operator/email/digest | Unread digest |
| POST | /api/operator/email/drafts:propose | Draft approval proposal |
| GET | /api/operator/approvals/pending | Pending approvals |
| POST | /api/operator/actions:propose | Allowlisted tool proposal |
| GET | /api/operator/repos/map | Repo registry summary |

Auth: loopback trust. Disabled → HTTP 404 `OPERATOR_DISABLED`.
