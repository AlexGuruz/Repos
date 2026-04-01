# M6B · Staleness Detection Rules

Version: 0.1.0  
Scope: All repos under `AI_LAB_GOVERNANCE_ROOT` and watched paths.  
Consumer: DocSync agent → proposal engine → command center UI (Capacitor app).

---

## 1. What "stale" means

A documentation node is **stale** when the code it describes has drifted beyond
the allowed thresholds below, and no approved update proposal covers the drift.

A documentation node is **current** when:
- Its `last_verified_commit` is within `MAX_DRIFT_COMMITS` of HEAD, **and**
- No unacknowledged trigger has fired against it.

---

## 2. Trigger taxonomy

Every trigger has a **severity** (INFO · WARN · CRITICAL) and a **confidence**
(LOW · MEDIUM · HIGH). Severity drives badge colour in the command center.
Confidence drives whether the agent auto-proposes or asks first.

### T1 — Symbol added or removed
| Field | Value |
|---|---|
| Trigger | A public function, class, method, or exported constant appears in or disappears from the AST diff between `last_verified_commit` and HEAD |
| Severity | WARN (removed) · INFO (added) |
| Confidence | HIGH |
| Staleness threshold | 1 commit — zero tolerance |
| Auto-propose | Yes |
| Docs targets | API reference, module README, changelog, any doc that `@mentions` the symbol |

**Detection method:** AST diff via `tree-sitter` or language-specific parser.  
**False-positive guard:** Private symbols (leading `_`, unexported lowercase Go, `#private` JS) are excluded unless they appear in existing docs.

---

### T2 — Function / method signature changed
| Field | Value |
|---|---|
| Trigger | Parameter name, type annotation, return type, or default value changes |
| Severity | WARN |
| Confidence | HIGH |
| Staleness threshold | 1 commit |
| Auto-propose | Yes |
| Docs targets | Docstring, API reference, usage examples, any doc containing the old signature verbatim |

**Detection method:** AST diff — compare parameter lists at function node level.  
**False-positive guard:** Formatting-only changes (whitespace, comment reflow) are ignored.

---

### T3 — File moved or renamed
| Field | Value |
|---|---|
| Trigger | `git diff --name-status` shows `R` (rename) or `C` (copy) for a tracked source file |
| Severity | WARN |
| Confidence | HIGH |
| Staleness threshold | 1 commit |
| Auto-propose | Yes |
| Docs targets | Any doc containing the old path as a string literal, import path, or link |

**Detection method:** `git log --diff-filter=RC --name-status` since `last_verified_commit`.  
**False-positive guard:** Renames inside auto-generated directories (`__pycache__`, `dist/`, `.venv/`) are ignored.

---

### T4 — Feature flag or config key changed
| Field | Value |
|---|---|
| Trigger | A key in a registered config file (`*.env.example`, `settings.py`, `config.yaml`, `*.toml`, `*.json` under `config/`) is added, removed, or renamed |
| Severity | CRITICAL (removed or renamed) · INFO (added) |
| Confidence | MEDIUM |
| Staleness threshold | 1 commit |
| Auto-propose | Yes for CRITICAL; queue for INFO |
| Docs targets | `.env.example`, any `Configuration` section in README or runbook, deployment docs |

**Detection method:** Key-level diff of config files using structured parsers (dotenv, TOML, YAML, JSON).  
**False-positive guard:** Value changes alone (not key changes) do not trigger unless the key is documented with a specific allowed-values list.

---

## 3. Staleness scoring

Each stale node gets a **drift score** used to prioritise proposals in the UI.

```
drift_score = severity_weight × trigger_count × age_factor

severity_weight:  CRITICAL=3  WARN=2  INFO=1
trigger_count:    number of distinct triggers fired against this node
age_factor:       min(1.0 + (days_since_trigger / 7), 3.0)
```

Nodes with `drift_score >= 6` surface as CRITICAL in the command center sidebar.  
Nodes with `drift_score 3–5` surface as WARN.  
Nodes with `drift_score < 3` surface as INFO.

---

## 4. Exemptions

A doc node can be marked exempt from a specific trigger:

```yaml
# In the doc file's frontmatter
docsync:
  exempt:
    - trigger: T4
      reason: "Config key is intentionally undocumented (internal only)"
      expires: 2025-12-31
      approved_by: SG
```

Expired exemptions automatically reactivate the trigger.

---

## 5. Scan cadence

| Mode | Cadence | Trigger |
|---|---|---|
| Continuous (default) | On every `git push` to watched repos | Git hook → DocSync agent |
| Scheduled deep scan | Daily at 03:00 local | Cron / Windows Task Scheduler |
| Manual | On demand via command center "Run scan" button | API call to `/api/docsync/scan` |

---

## 6. Out of scope for M6B

The following are deferred to later milestones:

- Semantic drift (doc *meaning* vs code *behaviour*) — needs LLM evaluation pass
- Test coverage staleness — separate M7 concern
- Third-party dependency changelog tracking — M8
