# Email Sorter Runbook (Phase 1)

This runbook covers Gmail auth wiring and the Phase 1 dry-run backfill workflow.

## Required files (OAuth)

The integrated Gmail adapter lives in:
- `E:/Repos/ai-lab/Ai/Email-Inbox-Agent---Doo-Made/app/gmail_client.py`

It will attempt (in order):
1. `GOOGLE_CREDENTIALS_FILE` (env var)
2. Adapter config resolution (via adapter `load_config()`)
3. Legacy fallback under the adapter folder:
   - `Ai/Email-Inbox-Agent---Doo-Made/credentials.json`
   - `Ai/Email-Inbox-Agent---Doo-Made/token.json`

### Option A (fastest)

Copy these files into the adapter legacy folder:
- `E:/Repos/ai-lab/Ai/Email-Inbox-Agent---Doo-Made/credentials.json`
- `E:/Repos/ai-lab/Ai/Email-Inbox-Agent---Doo-Made/token.json`

### Option B (recommended: secrets outside adapter)

Set these environment variables:

PowerShell:
```powershell
$env:GOOGLE_CREDENTIALS_FILE="E:\Repos\ai-lab\secrets\gmail\credentials.json"
$env:GOOGLE_TOKEN_FILE="E:\Repos\ai-lab\secrets\gmail\token.json"
```

CMD:
```cmd
set GOOGLE_CREDENTIALS_FILE=E:\Repos\ai-lab\secrets\gmail\credentials.json
set GOOGLE_TOKEN_FILE=E:\Repos\ai-lab\secrets\gmail\token.json
```

Notes:
- Recommended paths should be absolute.
- If `GOOGLE_TOKEN_FILE` does not exist yet, the adapter will generate it during the first interactive run using the credentials file.

## Auth preflight (fail early)

Use this to confirm Gmail auth wiring before any mailbox work:
```bash
python -m email_sorter.discovery --auth-check
```

If credentials/token are missing, the error output includes:
- every credential/token candidate path it attempted (in order)
- which ones are missing

## First-run token generation flow

If `token.json` does not exist but `credentials.json` does:
1. Run Phase 1 dry-run backfill (or discovery) in an interactive session.
2. The adapter will start a local OAuth server (`run_local_server(port=0)`).
3. Complete Google consent in the browser.
4. The adapter writes `token.json` to the configured token path.

## Phase 1 workflow (dry-run only)

1. Label inventory / wiring sanity:
   ```bash
   python -m email_sorter.discovery
   ```
2. Preflight check (optional but recommended):
   ```bash
   python -m email_sorter.discovery --auth-check
   ```
3. Dry-run sample:
   ```bash
   python -m email_sorter.backfill --days 120 --dry-run --limit 100
   ```
4. Review artifacts:
   - `docs/EMAIL_BACKFILL_DRY_RUN_REPORT.md`
   - `logs/email_sorter/<run_id>.jsonl`

Do not enable `--apply` or daemon autosort until the report is reviewed.

## Live sort (`--apply`)

Runs against the **Gmail API** (not IMAP). Labels are resolved with `get_or_create_label_id`: **existing labels are reused; new ones are created only when a proposed label name does not exist** (normalized match). New **driver child** labels are still skipped unless the sorter marks `would_create_child`.

Prerequisites:
- `pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib` (or install `Ai/Email-Inbox-Agent---Doo-Made/requirements.txt`).
- OAuth: set `GOOGLE_CREDENTIALS_FILE` and `GOOGLE_TOKEN_FILE` (see above), or place `credentials.json` / `token.json` under `Ai/Email-Inbox-Agent---Doo-Made/`.

PowerShell example (adjust paths and optional LLM):

```powershell
$env:GOOGLE_CREDENTIALS_FILE="E:\path\to\credentials.json"
$env:GOOGLE_TOKEN_FILE="E:\path\to\token.json"
$env:LLM_BASE_URL="http://127.0.0.1:1234/v1"   # optional
Set-Location E:\Repos\ai-lab
python -m email_sorter.backfill --apply --days 120 --limit 100
```

- Omit `--dry-run` when using `--apply` (they are mutually exclusive).
- High-confidence items may **archive** (remove `INBOX`) per `_decide_label_actions`; review thresholds in `email_sorter/config/thresholds.yaml` if you want to change that.

## Permits vs LOADS (PilotCarLoads)

- **`LOADS`**: Deterministic Gmail label for **PilotCarLoads** mail (`team@pilotcarloads.com` / `@pilotcarloads.com`). Not the same as oversize **permit** documents.
- **`Permits`**: Not chosen by deterministic rules from subject/body/filename. You can **file into Permits manually** in Gmail anytime. Automated **`permits`** only when **AI** and/or **worker document intel** infer that a **PDF/image attachment is actually a permit** (text/OCR/vision). Set:
  - `WORKER_N8N_WORKFLOW_ID_EMAIL_DOC_INTEL` — n8n workflow that inspects attachment bytes.
  - Optional: `EMAIL_SORTER_WORKER_BEFORE_AI_UNCATEGORIZED_PDF` (default `1`) — for IMAP/Gmail paths, when the message is still **`uncategorized`** but has a PDF/image, run worker **before** the LLM so content-based routing can win.

