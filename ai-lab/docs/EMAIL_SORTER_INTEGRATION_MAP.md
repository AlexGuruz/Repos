# Email Sorter Integration Map

Date: 2026-03-18

This document maps where an “AI email sorter” should plug into the existing ecosystem in this workspace. It intentionally avoids re-implementing infrastructure; instead it identifies integration points and existing safety/audit patterns we should reuse.

## 1) IMAP / Gmail Adapter (existing message ingestion + label operations)

### 1.1 Gmail label operations + message fetch (recommended adapter)
- Repo: `E:/Repos/ai-lab/Ai/Email-Inbox-Agent---Doo-Made/`
- Primary ingestion + actions: `app/gmail_client.py`
  - Fetch unread messages via Gmail API (INBOX + UNREAD by default):
    - `fetch_unread_emails(...)` uses `service.users().messages().list(userId="me", labelIds=["INBOX","UNREAD"], ...)`
  - Read message details:
    - `get_email_by_id(message_id)` calls `service.users().messages().get(format="full")` and extracts headers + text/plain (or HTML).
  - Apply labels safely:
    - `get_or_create_label_id(label_name)` creates missing labels, but tries to resolve existing labels via normalization:
      - `resolve_existing_label_name(label_name)` + `_normalize_label_name(...)`
    - `apply_action_label(...)`, `add_label_to_message(...)`, `remove_label_from_message(...)`
  - Delete is not part of the “triage” logic; label cleanup is a separate explicit command:
    - `cleanup_labels.py` (legacy labels deletion is opt-in and supports `--dry-run`)
  - Key integration hook:
    - Use the same label-resolution and “create only if missing” behavior, but extend with:
      - audit logging per email
      - optional archive action (Gmail “archive” is not implemented in this adapter yet)

### 1.2 IMAP message polling (existing IMAP adapter; currently used for route ingestion)
- Repo: `E:/Repos/geomapper app/`
- Poller: `poller.py`
  - Uses stdlib `imaplib.IMAP4_SSL(...)`, `conn.login(...)`, `conn.select(...)`
  - Fetches messages with UID tracking persisted in:
    - `data/poller_state.json` (`last_seen_uid`)
  - Parses email bodies into route fields (PilotCar Loads Map use-case)
  - Writes debug log:
    - `data/poll_log.txt`
  - Safety note:
    - This poller does not manage Gmail labels or archive/delete.
  - Integration hook:
    - Can be extended for “email_sorter” if desired, but it currently does not support label/archiving operations.

## 2) AI Orchestration (main “brain” entrypoints)

### 2.1 Main orchestrator runtime entrypoint
- Repo: `E:/Repos/ai-lab/`
- Entry point: `brain/orchestrator/main.py`
  - Function: `run(message: str, llm_base_url: str|None, llm_model: str|None, session_id="default") -> dict`
  - Responsibilities:
    - Intent classification and policy routing (`brain/router/router.py`)
    - Evidence loading/fusion (`brain/orchestrator/evidence_loader.py`, `evidence_fusion.py`)
    - Builds a grounded prompt block (`build_grounded_response(...)`)
    - Calls model via `brain/llm_client.py` (`chat_completion(...)`)
    - Applies “Guru workflow rules” from:
      - `E:/Repos/ai-lab/memory/workflow_rules.json` (loaded at runtime)
  - Logging:
    - Writes per-turn trace with `brain.telemetry.log_event(...)`

### 2.2 Approval gate (for tool execution / state-changing operations)
- Repo: `E:/Repos/ai-lab/`
- Approval gate module: `brain/orchestrator/approval_gate.py`
  - `requires_approval(action, tool=None)` decides if an action needs manual approval.

### 2.3 Approval queue persistence (manual approval control mechanism)
- Repo: `E:/Repos/ai-lab/`
- Approval queue: `brain/approval_queue/queue.py`
  - `submit(spec)` -> returns `approval-<n>` id
  - Pending approvals persisted to:
    - `E:/Repos/ai-lab/logs/approval_logs/pending.json`
  - Resolution persisted to:
    - `E:/Repos/ai-lab/logs/approval_logs/resolved_*.json`

### 2.4 Evidence + transparency/audit support
- Repo: `E:/Repos/ai-lab/`
  - Evidence schemas:
    - `brain/schemas/evidence.py`
  - Routing schema:
    - `brain/schemas/routing.py`
  - Telemetry logging:
    - `brain/telemetry.py` writes to `E:/Repos/ai-lab/logs/telemetry.jsonl`
  - Execution logs (when orchestrator runs registered tools):
    - `brain/execution.py` writes to `E:/Repos/ai-lab/logs/execution_logs/<tool_name>_<timestamp>.json`

## 3) Worker Node Interfaces (how heavy doc tasks are offloaded)

### 3.1 Worker tunnel + port expectations (how the main rig talks to worker)
- Repo: `E:/Repos/ai-lab/`
- Worker registry: `ops/registry/workers.yaml`
  - Worker assistant service:
    - `worker_assistant`: `http://127.0.0.1:8765` (health path `/health`)
  - n8n:
    - `http://127.0.0.1:5678` (health path `/`)
  - Ollama:
    - `http://127.0.0.1:11434` (health path `/api/tags`)
- Main-rig worker reachability checks:
  - `brain/worker_tunnel.py` -> `get_tunnel_status(...)` tests local port open status.

### 3.2 Worker Assistant HTTP client surface
- Repo: `E:/Repos/ai-lab/`
- Clients: `brain/worker_clients.py`
  - Health:
    - `worker_assistant_health(...)` calls `GET /health`
  - Index:
    - `worker_assistant_index_repo(repo_path, worker_name=...)` posts to `POST /index_repo`
  - Retrieval:
    - `worker_assistant_retrieve(query, worker_name=...)` posts to `POST /retrieve`

### 3.3 n8n workflow trigger (general offload mechanism)
- Repo: `E:/Repos/ai-lab/`
- Clients: `brain/worker_clients.py`
  - `worker_n8n_trigger(workflow_id, payload, worker_name=...)`
    - POST pattern: `/<webhook|webhook-test>/{workflow_id}` (implementation uses `path = f"/webhook/{workflow_id}"`)

### 3.4 OCR/document classification workflow IDs
Observation from repo scan:
- `E:/Repos/ai-lab/registry/workflows.json` is empty (`[]`).
- `E:/Repos/ai-lab/registry/scripts.json` only contains a few unrelated tools (e.g. rules sheet + growflow sales).

Integration impact:
- The “heavy document OCR / scanned permit parsing” interface (workflow IDs or endpoints) is not discoverable from the local registry.
- For email sorting, heavy doc handling must be implemented by:
  - either calling a known worker endpoint (not currently documented in repo), or
  - triggering a worker n8n workflow once the correct `workflow_id` is confirmed from worker-side setup.

## 4) Background jobs / watchers (existing continuous execution patterns)

### 4.1 Email agent scheduling (run-per-execution + external scheduler)
- Repo: `E:/Repos/ai-lab/Ai/Email-Inbox-Agent---Doo-Made/`
  - README instructs:
    - Windows: Task Scheduler helper scripts to run every N minutes
    - macOS: launchd helper scripts to run periodically

### 4.2 Command center / repo watcher (general background orchestration)
- Repo: `E:/Repos/ai-lab/command-center/command-center/`
  - Contains backend services for worker monitoring and repo watching.

Integration note:
- For the “autosort --daemon” requirement, either:
  - implement as a long-running loop in the email_sorter package (safe-mode with bounded batch size), or
  - reuse the command-center worker health patterns and run-per-execution + scheduler scripts.

## 5) Config system (yaml/json/env)

### 5.1 ai-lab command-center/brain settings
- `E:/Repos/ai-lab/command-center/command-center/backend/core/config.py`
  - Uses `pydantic_settings.BaseSettings`
  - Reads from `.env` and env vars
  - Key worker routing settings:
    - `worker_tunnel_url`, `WORKER_ASSISTANT_URL`, `WORKER_N8N_URL`, `OLLAMA_HOST` (with registry fallbacks)

### 5.2 ai-lab email inbox agent settings (.env)
- Repo: `E:/Repos/ai-lab/Ai/Email-Inbox-Agent---Doo-Made/app/config.py`
  - `load_config()` reads:
    - model backend settings: `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL_TRIAGE`, etc.
    - safety gates: `SUSPICIOUS_CONFIDENCE_THRESHOLD`, etc.
    - Gmail OAuth files: `GOOGLE_CREDENTIALS_FILE`, `GOOGLE_TOKEN_FILE`
    - runtime labeling flags and mapping:
      - `LABEL_*` variables map “topic categories” to actual Gmail labels.

### 5.3 geomapper app settings (config.json + env overrides)
- Repo: `E:/Repos/geomapper app/`
  - `config.json` for IMAP credentials (and geocode settings)
  - `.env` / secrets loader for Supabase credentials:
    - `backend/supabase_client.py` (reads `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`)

## 6) Logging / audit evidence (existing patterns)

### 6.1 Telemetry log (AI system)
- Repo: `E:/Repos/ai-lab/`
  - `brain/telemetry.log_event(...)` appends JSON-lines to:
    - `E:/Repos/ai-lab/logs/telemetry.jsonl`
  - Used for:
    - worker health checks
    - worker service call/fail events
    - orchestrator turn traces

### 6.2 Approval logs (manual approvals)
- Repo: `E:/Repos/ai-lab/`
  - `logs/approval_logs/pending.json`
  - `logs/approval_logs/resolved_<id>.json`

### 6.3 Execution logs (registered script tool runs)
- Repo: `E:/Repos/ai-lab/`
  - `logs/execution_logs/<tool_name>_<timestamp>.json`

### 6.4 Gmail action audit
Current state:
- `Ai/Email-Inbox-Agent---Doo-Made` logs counts and per-message actions via Python logging, but does not write a structured “per-email audit evidence file”.

Integration impact:
- The email sorter implementation must add structured audit logging for each action:
  - email id, subject, sender
  - category + confidence
  - labels applied
  - archived? (true/false)
  - AI used? worker used? (true/false)
  - evidence/reasons (rule hits + model reasons)

## 7) Approval / gating in the “permit ingestion” backend (geomapper app)

While the Gmail sorter is a separate layer (Gmail labels + archive), the backend already has a “raw intake -> candidate -> review -> approve -> job” safety gate we should mirror for “permit detection”.

- Repo: `E:/Repos/geomapper app/`
  - Document ingestion and review:
    - `backend/ingestion.py`
      - `create_ingestion_document(...)` creates `ingestion_documents` row.
      - `parse_ingestion_document(...)` extracts PDF text and sets:
        - `processing_status` to `parsed_ready_for_review` vs `parsed_partial` vs `failed`
        - `review_status` to `needs_review` vs `insufficient_data`
      - `approve_permit_candidate(...)` updates `review_status` to `approved`
      - `reject_permit_candidate(...)` updates `review_status` to `rejected`
    - `server.py` exposes API endpoints:
      - `POST /api/ingestion-documents`
      - `POST /api/ingestion-documents/:id/parse`
      - `POST /api/permit-candidates/:id/approve`
      - `POST /api/permit-candidates/:id/reject`
      - `POST /api/permit-candidates/:id/create-job` (requires approved candidates)

Integration note for email sorter:
- Gmail sorter’s “Needs Review” label + “never archive low confidence” mirrors the backend’s “approved-only -> job creation” rule.

## 8) Stored knowledge (drivers, companies, etc.)

### 8.1 Drivers list
- Repo: `E:/Repos/geomapper app/`
  - `data/drivers.json` (static fallback)
  - Supabase table `driver_profiles` (Phase 1+)

### 8.2 Permit ingestion extracted fields
- Repo: `E:/Repos/geomapper app/`
  - `backend/ingestion.py` stores extracted text (currently PDF text extraction):
    - `ingestion_documents.raw_text`, `parse_notes`, etc.
    - `permit_candidates.*` fields (origin/destination, route text, review status)

### 8.3 Orchestrator policy / workflow rules
- Repo: `E:/Repos/ai-lab/`
  - `policy/allowlists.yaml` affects orchestrator conversational openers.
  - `memory/workflow_rules.json` affects orchestrator behavior and transparency/proposals.

## 9) Integration “wiring diagram” (how the email sorter should plug in)

Proposed wiring using discovered integration points (no new infrastructure):

1. Message acquisition:
   - Use Gmail adapter in `Ai/Email-Inbox-Agent---Doo-Made/app/gmail_client.py` for:
     - unread inbox scanning with optional subject filter
     - safe label operations (resolve existing names + create if missing)
2. Deterministic classification layer:
   - implement local keyword/sender/attachment-pattern rules (fast + auditable)
3. AI classifier layer:
   - call `brain/orchestrator/main.py:run(...)` as the “main model”
   - require the classifier wrapper to extract/parse strict JSON-only output (or robustly locate JSON in mixed output)
4. Worker escalation (heavy doc tasks):
   - if attachments are scanned / unclear, offload via worker interfaces:
     - either a worker endpoint (not discoverable from local registry), or
     - `brain/worker_clients.py:worker_n8n_trigger(workflow_id, payload)` once workflow id is known
5. Decision layer:
   - apply confidence thresholds:
     - high confidence: apply category labels + archive (Gmail archive; must be implemented)
     - medium: apply label + `Needs Review` (no archive)
     - low: `Needs Review` only (leave in inbox)
6. Action layer:
   - use `gmail_client.py` label functions for “apply labels”
   - implement “archive” and “never delete” semantics
7. Audit logging:
   - add a per-message JSON log file (new) and also emit `brain.telemetry.log_event(...)` entries for correlation

