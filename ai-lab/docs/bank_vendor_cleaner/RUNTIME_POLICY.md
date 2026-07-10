# Bank Vendor Cleaner — local runtime policy

**Audience:** Local LLM (Qwen / LM Studio) used as a **reasoning helper only**.  
**Authority:** Deterministic pipeline (`brain/bank_vendor_cleaner/engine.py`, `scripts/sheet_label_pipeline.py`) owns all production writes.

**Primary Qwen prompt:** [`QWEN_OPERATING_PROMPT.md`](QWEN_OPERATING_PROMPT.md) (injected by orchestrator). This file adds confidence handling, memory bucket detail, and code mapping. Never use either file to bypass the deterministic write path.

---

## 1. Processing order

For each row, process in this order:

### Boundary check

- Only process rows from C2 through the last nonblank source row.
- Never write below that boundary.

### Blank-row check

- If source cell is blank, preserve alignment and write blank outputs for that row.

### Alias-memory check first

- Exact raw-string match
- Normalized raw-string match
- Known merchant-location alias match

### Deterministic label classification

Fixed event labels first:

- deposit
- transfer in / transfer out
- ATM withdrawal
- loan / payment / reversal types

Then merchant/platform rules, then fallback merchant cleanup.

### Location extraction before destructive cleanup

- Pull City/State from the raw string **before** stripping trailing tokens.

### Recovery pass

- If label unclear: use alias memory + known pattern families.
- If location unclear: use merchant-location memory + trailing token patterns.

### Write plain text values only

- Column C = final canonical label
- Column D = final City/State text
- Never formula output

---

## 2. Decision priority ladder

Closest practical “thinking” without exposing hidden reasoning.

### Label priority

1. Existing approved alias
2. Fixed transaction-type rule
3. Known merchant family pattern
4. Known platform/entity pattern
5. Deterministic fallback cleanup
6. Optional web/vendor lookup
7. Unknown Merchant

### Location priority

1. Existing approved alias-location mapping
2. Clear trailing `City ST`
3. Clear trailing `City StateName`
4. Address + city/state pattern
5. Known shortened city expansion
6. State-only fallback
7. Blank

---

## 3. What to optimize for (in order)

1. Consistency across runs
2. Sortable canonical outputs
3. Row alignment correctness
4. Single-sheet safety
5. Plain-text write safety
6. Coverage of noisy merchant/location variants
7. Only then completeness

Prefer a **stable slightly-generic label** over a clever but unstable guess.

| Better | Worse |
|--------|-------|
| Murphy | Murphy 7440 Walmart Fuel |

---

## 4. Practical heuristics

### Canonical label style

- 1–3 words
- Title case
- Brand/entity/event name only
- No dates, phone numbers, sequence IDs, addresses, or city/state in label
- No formulas ever

### City/State style

- `City, ST` if both known
- `ST` if only state known
- Blank if not reliable after recovery
- Never guess from weak evidence

---

## 5. When to trust deterministic rules over model judgment

**Always prefer deterministic rules for:**

- Walmart family
- Murphy family
- Spotify
- Kraken
- Coinbase
- eToro
- OK Gov
- OMMA License
- Deposits / transfers / withdrawals / payments

**Use model judgment only for:**

- Unresolved merchants
- Badly truncated merchants
- City abbreviation recovery when not covered by alias memory
- Vendor web lookup interpretation

Even then:

1. Model suggests
2. Cache / approval promotes
3. Future runs become deterministic

---

## 6. Error-avoidance rules

The local model must never:

- Output a formula
- Output sheet references
- Infer another spreadsheet
- Reorder rows
- Dedupe rows before writing
- Continue past last nonblank source row
- Overwrite outside columns C and D
- Use web lookup as direct write authority

---

## 7. Confidence handling

### High confidence

- Exact alias match
- Fixed deterministic regex match
- Clear city/state pattern

### Medium confidence

- Merchant family match with noisy suffixes
- Known abbreviation expansion
- State-only location

### Low confidence

- Unresolved merchant inferred from partial text
- City inferred from weak/truncated clue
- Web lookup candidate without alias confirmation

### Write policy

| Confidence | Label | City/State |
|------------|-------|------------|
| High | Write | Write |
| Medium | Write if deterministic fallback exists | Write |
| Low | Conservative fallback allowed | Prefer blank over guessing |

Production writes are made by the deterministic pipeline using these rules. The model may **recommend**; it does not **commit**.

---

## 8. Internal reasoning template (do not expose to users)

For each row:

- Is row inside active boundary?
- Is row blank?
- Is there an approved alias match?
- Is this a fixed event type?
- Is there a merchant family match?
- Extract location before cleanup.
- Can location be recovered from alias memory?
- Produce final canonical label.
- Produce final City/State.
- Validate outputs are plain text only.
- Write only within row-aligned boundary.

---

## 9. Memory buckets

See `config/bank_vendor_cleaner/memory_buckets.yaml` for file paths.

| Bucket | Purpose |
|--------|---------|
| `canonical_aliases` | Approved raw → label (+ optional location) |
| `merchant_location_patterns` | Canonical label → default city/state |
| `fixed_event_labels` | Non-merchant transaction types |
| `rejected_aliases` | Blocked suggestions; do not promote |
| `manual_review_pending` | Lookup / model suggestions awaiting approval |

Promotion flow: `manual_review_pending` → human approval → `canonical_aliases` → next run is deterministic.

---

## 10. The five behaviors to preserve

If you only preserve five things, preserve these:

1. Alias memory first
2. Location extraction before cleanup
3. Fixed event labels before merchant inference
4. Plain-value-only writes
5. Strict row-boundary + row-order preservation

---

## Implementation map (code, not LLM)

| Policy section | Implementation |
|----------------|----------------|
| Boundary / blank rows | `process_rows()`, `find_last_nonblank_row()` in `engine.py`; `sheet_label_pipeline.py` |
| Alias memory | `memory_alias_map.yaml`, `build_alias_lookup()`, `get_label_with_source()` |
| Rules / fallback | `CANONICAL_RULES`, `cleaning_rules.yaml`, `deterministic_fallback()` |
| Location | `extract_city_state()`, `known_city_state_overrides.yaml` |
| Plain-text writes | `assert_plain_values()`, Sheets `RAW` mode |
| Vendor lookup (suggest only) | `vendor_lookup.py`, `vendor_lookup_worker.py` |
| Rejected / pending | `rejected_aliases.yaml`, `vendor_lookup_cache.yaml`, `vendor_lookup_review_queue.json` |

**Note:** `CANONICAL_RULES` in `engine.py` interleaves some merchant patterns before fixed-event patterns after the alias pass. Alias memory still wins first. Reordering rules for stricter fixed-event-first parity is a separate engine change.
