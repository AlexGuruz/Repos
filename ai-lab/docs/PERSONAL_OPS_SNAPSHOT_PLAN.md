# Personal Ops Snapshot Plan (Phase 2)

## Goal (scoped)

Make `personal_ops_snapshot` **useful for daily planning**: calendar horizon, repo activity, agenda cues, and optional worker/Kylo signals — without turning the whole assistant into a full personal-ops product.

## What changed

### Builder (`brain/prepared_context/builders.py::build_personal_ops_snapshot`)

1. **Config**
   - Reads `config/personal_ops.yaml` first, then `config/personal_ops.example.yaml`.
   - Surfaces `config_path` in snapshot `data` and adds an `evidence_items` row for the loaded file.

2. **Repo pulse (git idle)**
   - Uses `lib.repo_staleness.scan_repos` with the `repos` list from config (same shape as `personal_ops_daily_digest.py`).
   - Populates `data.repo_pulse` and `data.stale_repo_labels` using `stale_warning_days`.

3. **Calendar (optional)**
   - If `calendar.primary` / `calendar_id` is set and Google client libraries + OAuth token exist, pulls a short horizon (default **7 days**) via `lib.google_calendar_client.list_events`.
   - Populates `calendar_today`, `calendar_upcoming`, and combined `calendar_events`.
   - Failures are **non-fatal** (`errors[]` only); snapshot still builds.

4. **Kylo heartbeats**
   - Reads `kylo_heartbeats[]` paths from config (same semantics as the digest script) into `data.kylo_heartbeats`.

5. **Project agenda merge**
   - If `state/prepared_context/project_agenda.json` exists (from a prior `project_agenda` build), merges `today_focus`, priorities, blocked/overdue, and next actions into `data.project_focus` and planning lists.

6. **Evidence + confidence**
   - Multiple `evidence_items` (config, scripts, repo pulse, calendar, cached agenda).
   - Confidence is lowered when almost no planning signals exist (e.g. missing config).

### Loader (`brain/prepared_context/loader.py`)

- Snapshot selection for personal planning widened (`focus on today`, `repos are stale`, etc.).
- **Disambiguation:** removed the loose substring `work on today` from the `project_agenda` matcher so phrases like **“what should I focus on today?”** route to `personal_ops_snapshot` instead of being swallowed by the agenda/repo pair.

## How to verify

1. **Config + git**
   - Copy `config/personal_ops.example.yaml` → `config/personal_ops.yaml` and set real `repos` paths.
   - Run `python scripts/build_prepared_context.py --snapshot personal_ops_snapshot` (or full refresh).
   - Inspect `state/prepared_context/personal_ops_snapshot.json`: expect non-empty `repo_pulse` when repos are valid git checkouts.

2. **Calendar**
   - After OAuth token exists for Calendar, ensure `calendar` block is set in YAML.
   - Rebuild snapshot; confirm `calendar_events` / `calendar_today` populate or `errors` explains preflight failure.

3. **Chat**
   - Ask: “what should I focus on today?” with snapshots built — expect `personal_ops_snapshot` in the prepared-context reply.

4. **Automated tests**
   - `pytest tests/test_personal_ops_snapshot.py -q`

## Governance

- Snapshot build is **read-only** for calendar and git; it does not send Telegram or stamp calendar events (those remain in `personal_ops_daily_digest.py` with explicit flags).

## Roadmap note

Phase 1 acceptance and the **tool_registry metadata governance** watch-item are recorded in `docs/ROADMAP_PHASE_NOTES.md`.
