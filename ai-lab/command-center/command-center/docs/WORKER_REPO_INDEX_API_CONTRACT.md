# Worker Assistant API contract — repo index hub (command-center)

**Audience:** Cursor agent on the **worker rig** implementing `worker_assistant` (FastAPI, typically port **8765**).

**Transport from main rig:** command-center posts to `{WORKER_TUNNEL_URL}/{op}` with JSON body (see `backend/services/supervisor_bridge.py`). Paths are **without** leading slash in the URL join (e.g. `POST http://127.0.0.1:8765/index_repo`).

**Hub behavior:** After `index_repo`, command-center parses your JSON (see `backend/services/repo_index_coordinator.py`), validates **required metadata**, runs `retrieve` with **`target: staging`** as a smoke test, then calls `promote_repo_index`. User/agent retrieval stays on **active** until promote succeeds.

**Timeouts:** Default worker tunnel timeout is **30s** except **`index_repo`** and **`promote_repo_index`** use **900s** (`worker_bridge_timeout_seconds` / `worker_bridge_index_repo_timeout_seconds` in hub settings / env).

---

## 1) `POST /index_repo`

### Request body (JSON)

Command-center sends:

```json
{
  "repo_id": "ai-lab",
  "target": "staging",
  "mode": "incremental",
  "force_full": false,
  "expected_policy_hash": "sha256:…",
  "expected_embedding_model_id": "bge-small-en-v1.5",
  "expected_embedding_model_revision": "2026-03-01",
  "expected_index_schema_version": 3,
  "expected_collection_layout_version": 1
}
```

| Field | Type | Required | Notes |
|-------|------|----------|--------|
| `repo_id` | string | yes | Top-level folder name under watched root, or your registry id. |
| `target` | string | hub: yes | Omit `target` only for **legacy** direct-upsert jobs (scheduled tooling); hub always sends `"staging"`. |
| `mode` | string | yes | `"incremental"` \| `"repo_refresh"` \| `"full_rebuild"`. |
| `force_full` | boolean | yes | If true, full rebuild into staging (after approval flows on hub). |
| `expected_policy_hash` | string | no | **Raw-file** SHA-256 (see Policy hash below). |
| `expected_embedding_model_id` | string | no | For worker logging / optional checks. |
| `expected_embedding_model_revision` | string | no | Same. |
| `expected_index_schema_version` | integer | no | Same. |
| `expected_collection_layout_version` | integer | no | Same. |

### Response body (JSON)

**Implemented worker shape (SuccessResponse):** top-level `ok`, `task`, `warnings`, `errors`, and **`meta`** with all required index fields. Command-center merges **`result.meta`** with top-level `result` keys when parsing.

Command-center reads **`result`** from its bridge wrapper: `{ "ok": true, "result": <YOUR_JSON> }`. So either:

- Put required index fields under **`YOUR_JSON.meta`** (recommended), **or**
- Put them at the top level of `YOUR_JSON` (hub merges `result` and `result.meta`).

**Required for strict hub validation** (missing any ⇒ **Gate A** — approval for full rebuild):

| Field | Type | Notes |
|-------|------|--------|
| `repo_id` | string | Echo. |
| `target` | string | Must be `"staging"`. |
| `build_id` | string | Unique per build (or use `id`). |
| `staging_version` | string | Opaque version id for this staging snapshot (e.g. `gen_20260319_1620`). |
| `active_version_seen` | string \| null | Active pointer at build start (null if none). |
| `embedding_model_id_used` | string | Non-empty. |
| `embedding_model_revision_used` | string | Non-empty (e.g. `"2026-03-01"`). |
| `policy_hash_used` | string | Non-empty; must match hub `config/index_policy.yaml` derived hash if build is valid. |
| `index_schema_version_used` | integer | Must match hub policy. |
| `collection_layout_version_used` | integer | Must match hub policy. |
| `metadata_readable` | boolean | `false` if index manifest unreadable. |
| `corruption_detected` | boolean | `true` if integrity check failed. |

**Strongly recommended:**

| Field | Type |
|-------|------|
| `files_considered` | integer |
| `files_indexed` | integer |
| `chunks_indexed` | integer |
| `started_at` | string (ISO8601 UTC) |
| `finished_at` | string (ISO8601 UTC) |
| `warnings` | string[] |
| `errors` | string[] |

### Example response (minimal valid shape)

```json
{
  "ok": true,
  "meta": {
    "repo_id": "ai-lab",
    "target": "staging",
    "build_id": "build_abc123",
    "staging_version": "gen_20260319_1620",
    "active_version_seen": "gen_20260318_0900",
    "embedding_model_id_used": "bge-small-en-v1.5",
    "embedding_model_revision_used": "2026-03-01",
    "policy_hash_used": "sha256:…",
    "index_schema_version_used": 3,
    "collection_layout_version_used": 1,
    "metadata_readable": true,
    "corruption_detected": false,
    "files_considered": 1200,
    "files_indexed": 1180,
    "chunks_indexed": 9400,
    "started_at": "2026-03-19T16:19:55Z",
    "finished_at": "2026-03-19T16:20:10Z"
  },
  "warnings": [],
  "errors": []
}
```

**Policy hash:** Hub and worker must agree on **the same bytes** of `index_policy.yaml` and use **`sha256:` + hex(SHA-256(raw file bytes))**. Command-center: `compute_policy_hash_file()` in `services/index_policy.py` via `get_expected_policy_identity()`. Copy the hub YAML to the worker (or keep them byte-identical) so `policy_hash_used` passes Gate C validation.

**Embedding IDs:** Hub `config/index_policy.yaml` uses `embedding_model_id` / `embedding_model_revision` for strict equality checks — keep worker policy YAML and hub YAML aligned (e.g. both `bge-small-en-v1.5` or both nomic IDs).

---

## 2) `POST /promote_repo_index`

### Request body (JSON)

```json
{
  "repo_id": "ai-lab",
  "staging_version": "gen_20260319_1620"
}
```

### Behavior

- **Atomically** point **active** retrieval at the completed staging snapshot identified by `staging_version`.
- Reject promote if `staging_version` is unknown, incomplete, or failed validation.
- Keep **previous active** version id available for rollback (worker-internal).

### Response (JSON)

Hub accepts any JSON; useful fields:

```json
{
  "ok": true,
  "repo_id": "ai-lab",
  "active_version": "gen_20260319_1620",
  "previous_active_version": "gen_20260318_0900",
  "promoted_at": "2026-03-19T16:20:12Z"
}
```

---

## 3) `POST /retrieve`

### Request body (JSON)

Pre-promote **smoke test** from the hub coordinator:

```json
{
  "query": "where is repo watcher started",
  "target": "staging"
}
```

Interactive / other callers may send only `query` (default **`target: active`**).

| Field | Type | Required |
|-------|------|----------|
| `query` | string | yes |
| `target` | string | no — `"active"` (default) or `"staging"`. |

| `target` | Meaning |
|----------|---------|
| `active` (default) | Production retrieval. |
| `staging` | Query staging index only (must not change active pointer). |

---

## 4) `GET /repo_status` (recommended)

Query params or JSON body (your choice; document one):

Example: `GET /repo_status?repo_id=ai-lab`

### Response (JSON)

Return **actual** built state for the repo (both pointers if applicable):

```json
{
  "repo_id": "ai-lab",
  "active_version": "gen_20260318_0900",
  "staging_version": "gen_20260319_1620",
  "embedding_model_id_used": "bge-small-en-v1.5",
  "embedding_model_revision_used": "2026-03-01",
  "policy_hash_used": "sha256:…",
  "index_schema_version_used": 3,
  "collection_layout_version_used": 1,
  "metadata_readable": true,
  "corruption_detected": false,
  "doc_count": 18234,
  "vector_count": 44109,
  "built_at": "2026-03-19T16:20:00Z",
  "index_generation_id": "gen_20260319_1620"
}
```

---

## 5) Implementation checklist for worker agent

- [ ] `POST /index_repo` with `target=staging` builds **only** staging; never mutates active vectors during staging build.
- [ ] Response includes **all required metadata** fields (section 1) or hub will block with Gate A.
- [ ] `policy_hash_used` matches hub manifest after a successful build.
- [ ] `POST /promote_repo_index` performs **atomic** active pointer update.
- [ ] `POST /retrieve` defaults to **active**; optional `target=staging` for smoke tests.
- [ ] `GET /health` still works; `GET /repo_status` implemented for debugging and drift checks.
- [ ] Hub uses **900s** timeout for `index_repo` by default; other worker ops stay at **30s**.

---

## 6) Hub reference files

| Purpose | Path |
|---------|------|
| Desired policy manifest | `command-center/config/index_policy.yaml` |
| Policy hash + identity (raw file bytes) | `command-center/backend/services/index_policy.py` |
| Coordinator + validation | `command-center/backend/services/repo_index_coordinator.py` |
| HTTP bridge to worker | `command-center/backend/services/supervisor_bridge.py` |
| Hub status | `GET /api/repo/index_state` (optional `?worker_repo_id=` merges worker `/repo_status`) |

---

## 7) Quick manual test (from main rig, tunnel up)

```powershell
$base = "http://127.0.0.1:8765"
$body = @{
  repo_id = "ai-lab"
  target = "staging"
  mode = "incremental"
  force_full = $false
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri "$base/index_repo" -Body $body -ContentType "application/json"
```

Verify response includes every **required** field in section 1.
