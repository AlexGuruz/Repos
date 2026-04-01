# M6B · Proposal Card Templates

These are the exact card formats the DocSync agent must emit into the
command center chat. The Capacitor app renders them natively on the phone.
All fields in `{braces}` are substituted at generation time.

---

## T1 — Symbol added

```
PROPOSAL · {id}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ INFO  · T1 · HIGH  
New symbol `{symbol_name}` needs documentation

`{symbol_name}` ({symbol_type}) was added to `{source_file}` in commit {short_sha}.
No documentation entry exists for it yet.
Affected doc(s): {doc_target_count}

Source: {short_sha} · {author} · {relative_time}
File:   {source_file}:{line_number}

Docs affected ({doc_target_count}):
  · {doc_target_1}
  · {doc_target_2}

[Approve] [Reject] [Defer] [Show diff]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## T1 — Symbol removed

```
PROPOSAL · {id}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠ WARN  · T1 · HIGH  
Remove docs for deleted symbol `{symbol_name}`

`{symbol_name}` ({symbol_type}) was removed from `{source_file}` in commit {short_sha}.
Existing documentation still references it and will mislead users.

Source: {short_sha} · {author} · {relative_time}
File:   {source_file}

Docs affected ({doc_target_count}):
  · {doc_target_1}

[Approve] [Reject] [Defer] [Show diff]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## T2 — Signature changed

```
PROPOSAL · {id}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠ WARN  · T2 · HIGH  
Update signature docs for `{symbol_name}`

`{symbol_name}` in `{source_file}` changed its signature in commit {short_sha}.
{changed_aspect} — documentation still shows the old signature.

  Before: {old_signature}
  After:  {new_signature}

Source: {short_sha} · {author} · {relative_time}
File:   {source_file}:{line_number}

Docs affected ({doc_target_count}):
  · {doc_target_1}

[Approve] [Reject] [Defer] [Show diff]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## T3 — File moved or renamed

```
PROPOSAL · {id}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠ WARN  · T3 · HIGH  
Update {doc_target_count} doc path reference(s) after rename

`{old_path}` was renamed to `{new_path}` in commit {short_sha}.
Docs still reference the old path and will produce broken links or imports.

Source: {short_sha} · {author} · {relative_time}
Rename: {old_path} → {new_path}

Docs affected ({doc_target_count}):
  · {doc_target_1}
  · {doc_target_2}

[Approve] [Reject] [Defer] [Show diff]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Batch variant (≥5 files):

```
PROPOSAL · {id}  [BATCH]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠ WARN  · T3 · HIGH  
Rename cascade — update {doc_target_count} path references

`{old_path}` renamed to `{new_path}`. {doc_target_count} doc files contain the
old path as a string literal, import, or link. One approval applies all.

Source: {short_sha} · {author} · {relative_time}

[Approve all] [Reject] [Defer] [Show full list]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## T4 — Config key removed or renamed (CRITICAL)

```
PROPOSAL · {id}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 CRITICAL  · T4 · HIGH  
Config key `{key_name}` removed — doc update required

`{key_name}` was {removed_or_renamed} in `{config_file}` in commit {short_sha}.
This key is documented in {doc_target_count} location(s). Stale docs will
cause operator errors on fresh deployments.

{rename_note}

Source: {short_sha} · {author} · {relative_time}
File:   {config_file}

Docs affected ({doc_target_count}):
  · {doc_target_1}
  · {doc_target_2}

[Approve] [Reject] [Defer] [Show diff]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## T4 — Config key added (INFO)

```
PROPOSAL · {id}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ INFO  · T4 · HIGH  
New config key `{key_name}` needs documentation

`{key_name}` was added to `{config_file}` in commit {short_sha}.
No documentation entry exists. Operators won't know it's available.

Default value: {default_value}

Source: {short_sha} · {author} · {relative_time}
File:   {config_file}

Docs affected ({doc_target_count}):
  · {doc_target_1}

[Approve] [Reject] [Defer] [Show diff]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Needs-human-draft variant (any trigger)

Used when `needs_human_draft: true`. Agent cannot generate the diff itself.

```
PROPOSAL · {id}  [NEEDS DRAFT]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{severity_icon} {severity}  · {trigger} · MEDIUM  
{title}

{summary}

I can detect the drift but cannot confidently draft the update.
Here's what I know:

  · {draft_hint_1}
  · {draft_hint_2}
  · {draft_hint_3}

Source: {short_sha} · {author} · {relative_time}
Docs:   {doc_target_1}

[Write it for me] [I'll edit] [Reject] [Defer]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Re-surfaced deferred proposal

```
↩ RE-SURFACED · Deferred {original_defer_date} · {days_deferred} days ago

PROPOSAL · {id}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{severity_icon} {severity}  · {trigger} · {confidence}  
{title}

{summary}

Drift score now: {drift_score}

[Approve] [Reject] [Defer again] [Show diff]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Escalation card (>7 days no decision)

```
⚠ ESCALATED · {days} days without a decision

PROPOSAL · {id}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{severity_icon} {severity}  · {trigger} · {confidence}  
{title}

{summary}

This proposal has been pending for {days} days.
Drift score: {drift_score}  (threshold for auto-escalation: 6)

[Approve] [Reject] [Defer] [Show diff]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Clean scan result

When no stale docs are found, emit exactly:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Drift scan complete · No stale documentation detected

Repos:    {repo_list}
Commits:  {n} since {short_sha}
Triggers: none fired
Next scan: {next_scan_datetime}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Low-confidence question card

When confidence=LOW, do not propose — ask first:

```
QUESTION · {trigger} · {source_file}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{one_sentence_change_description}

I detected a change but I'm not confident which documentation is affected.
Which doc file(s) should I check against this change?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
