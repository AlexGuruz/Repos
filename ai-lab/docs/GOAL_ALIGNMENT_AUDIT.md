# Goal Alignment Audit

Goal rubric: `already wired` / `partially wired` / `missing`.


| Goal                                        | Already wired                                                               | Partially wired                                        | Missing trigger/tool/UI/gate/data                                    | Recommended next action                                           |
| ------------------------------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------ | -------------------------------------------------------------------- | ----------------------------------------------------------------- |
| fast local assistant                        | prepared-context fast path in orchestrator; SSE streaming; route fast paths | phrase brittleness can miss prepared hits              | broaden semantic snapshot selection and tighten stale index accuracy | improve `_pick_snapshots_for_message` + stale recompute for index |
| prepared context for common answers         | builders/store/loader/refresher/API/UI all wired                            | personal_ops snapshot depth is weaker                  | richer personal_ops data feed and freshness evidence                 | enrich `build_personal_ops_snapshot` sources                      |
| repo documentation maintainer               | `repo_pulse` + doc/status phrasing routes + benchmark coverage              | still partially phrase-driven                          | stronger repo doc staleness metrics for all repos                    | add explicit repo docs freshness index builder fields             |
| repo script cleanup assistant               | tooling exists (repo scan/search + prepared repo pulse)                     | orphan detection not automated in runtime              | no persistent orphan dashboard view                                  | schedule periodic orphan inventory report generation              |
| personal calendar/daily assistant           | scripts exist + snapshot category exists                                    | not fully trigger-wired/scheduled by default           | command-center UX for personal ops outputs limited                   | wire one scheduled personal ops refresh source                    |
| ops copilot                                 | worker health + tools stats + approvals UI + feed bus                       | dual execution lanes increase policy drift             | unified policy enforcement at execution boundary                     | enforce approval gate in execution wrapper path                   |
| inventory/par system                        | Growflow scripts and exports exist                                          | integration into ai-lab runtime is limited             | missing canonical trigger map and registry exposure                  | define canonical Growflow runners + register read-safe tools      |
| consent-based customer product alert system | approval primitives and allowlist framework exist                           | no dedicated app-level workflow chain in current scope | missing explicit workflow, UI surface, and auditing views            | design approved workflow contract before implementation           |
| future file organization assistant          | repo index coordinator + watcher + retrieval groundwork exists              | organizer-specific tools absent                        | missing dedicated organizer tool + approval policy                   | defer until architecture phase after audit                        |


## Evidence

- Orchestrator and routing: `brain/orchestrator/main.py`, `brain/router/router.py`, `brain/orchestrator/routing_policy.py`
- Prepared context: `brain/prepared_context/*`, `command-center/backend/services/prepared_context_refresher.py`, `frontend/src/App.jsx`
- Approvals/allowlist: `brain/approval_queue/queue.py`, `brain/permanent_allowlist.py`, `backend/routers/events.py`
- Worker: `brain/worker_health.py`, `brain/worker_clients.py`, `backend/services/supervisor_bridge.py`
- Repo indexing: `backend/services/repo_index_coordinator.py`, `backend/services/repo_watcher.py`