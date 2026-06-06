# Bank Vendor Cleaner — vendor lookup (v2)

Optional add-on: resolve **unknown or low-confidence merchants** after deterministic cleaning fails.

**Worker:** `scripts/vendor_lookup_worker.py`  
**Engine:** `brain/bank_vendor_cleaner/vendor_lookup.py`  
**Never writes sheet columns C/D.**

---

## When lookup runs

All must be true:

- Deterministic pass used **fallback** (not alias or rule match)
- Raw row is nonblank and inside active write boundary
- Label is **not** a fixed event (Cash Deposit, Transfer In/Out, ATM Withdrawal, etc.)
- Not a formula cell

## Provider order

1. `vendor_lookup_cache.yaml` (local cache)
2. `mcp_web_search` / `brain.web_tool.web_search` (Tavily/Serper if configured)
3. `manual_review` queue

## Output shape

```json
{
  "raw_input": "",
  "candidate_label": "",
  "candidate_city": "",
  "candidate_state": "",
  "confidence": "low|medium|high",
  "evidence": [{"source": "", "match_reason": ""}],
  "decision": "cache_candidate|manual_review|reject"
}
```

## Approval flow

1. Deterministic pass fails → lookup runs
2. Result stored in `vendor_lookup_cache.yaml` **pending** and `reports/vendor_lookup_review_queue.json`
3. Human reviews; sets `approved: true` on cache entry
4. Promote approved entries into `memory_alias_map.yaml`:

```bash
python scripts/vendor_lookup_worker.py --raw-input "x" --promote-approved
```

5. Future runs resolve via deterministic alias map

## Hard rules

- Lookup **never** writes C/D
- `require_human_approval_for_new_aliases: true` (default)
- `allow_auto_promote_to_alias_map: false` (default)
- MCP/web results are suggestions only

## Commands

```bash
# Single row lookup (dry-run: no pending cache write)
python scripts/vendor_lookup_worker.py --raw-input "unknown merchant string" --dry-run

# Lookup and append to pending cache + review queue
python scripts/vendor_lookup_worker.py --raw-input "unknown merchant string" --no-dry-run

# Pipeline with optional lookup pass on unresolved rows
python scripts/sheet_label_pipeline.py --dry-run --vendor-lookup
```

## Config

| File | Purpose |
|------|---------|
| `vendor_lookup_rules.yaml` | Trigger rules, provider order |
| `vendor_lookup_cache.yaml` | Approved entries + pending |
| `vendor_lookup_providers.yaml` | Provider settings |
| `vendor_lookup_settings.example.env` | Env template |

## Failure handling

- No web provider configured → skip to manual_review
- Low confidence → `manual_review` only
- Lookup disabled → `reject` with reason in evidence

## Tests

```bash
pytest tests/test_vendor_lookup.py -q
```
