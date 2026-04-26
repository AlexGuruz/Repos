# AI model & prompt usefulness audit

Focus: **why** replies feel vague, over-cautious, or mis-grounded—and **concrete** code-level recommendations. Primary construction sites: `brain/orchestrator/main.py`, `brain/prompts/grounded_prompt.txt`, `brain/catalog_loader.py`, and `brain/llm_client.py`.

## Where prompts are built

| Piece | Location | Role |
|-------|----------|------|
| Grounded user block | `build_grounded_response()` in `main.py` | Fills `brain/prompts/grounded_prompt.txt` with key/secondary evidence, constraints, `answer_style`. |
| Catalog prepend | `format_catalog_grounding_for_message()` | Injects `## Lab system catalog` above the template when matchers hit. |
| LLM system message | `main.py` (default answer path, `if base_url:`) | Command Center persona, anti-hallucination rules, softened guidance to avoid blanket refusals. |
| LLM messages | `main.py` | `[system, user]` where `user` = raw user message + `evidence_block`. |

## Findings

### 1. Prompt can be large and “template-heavy”

- **Issue**: `grounded_prompt.txt` repeats section headers and constraints; combined with long ops registry text or README excerpts, **token count** grows quickly.
- **Effect**: Slower TTFT on local models; model may attend to boilerplate over facts.
- **Recommendation**: Add a **compact evidence mode** for chat: top-N bullet extract per `EvidenceItem`, cap total chars (e.g. 6–8k) *before* LLM, keep full blob in trace only.

### 2. Active topic `(none)` is not ambiguous to humans but confuses heuristics

- **Issue**: We previously treated substring `(none)` in the first ~1.2k chars as “no key evidence” for no-LLM replies—**false negative** because `Active Topic:\n(none)` is normal.
- **Status**: **Fixed** in `main.py` by checking `\nKey Evidence:\n(none)` instead.

### 3. Catalog vs session facts

- **Issue**: Lab catalog is **authoritative for component metadata** but not for “what did my last scan output.” Treating catalog presence as “sufficient session evidence” caused LLM calls that then failed → **generic fallback**.
- **Status**: **Fixed**—`insufficient_evidence` hard-stop no longer skipped merely because catalog appeared in `evidence_block`; catalog is appended to the conversational insufficient reply when helpful.

### 4. “Insufficient evidence” fusion vs user expectations

- **Issue**: `evidence_fusion.fuse_evidence` sets `insufficient_evidence` when there is truly no loaded evidence; internal keywords (e.g. “scan”) previously led to empty session artifacts → user still expects a **helpful nudge** (run scan, ops overview).
- **Status**: Improved via hard-stop copy in `main.py` + routing fast paths (`routing_policy.py`) for common doc/Growflow/lab questions.

### 5. Local LLM substitution for refusals

- **Code**: In `main.py`, if the model output contains “insufficient” + “evidence”, catalog components may **replace** the reply (`matching_components` / `format_component_grounding`).
- **Risk**: Can feel like non-sequitur if user asked something unrelated to catalog rows.
- **Recommendation**: Narrow substitution triggers (e.g. only when user message matched catalog intents) or gate on **confidence** from `matching_components`.

### 6. No-LLM “evidence dump” path

- **Issue**: When `base_url` is empty and key evidence exists, the user sees the **entire** grounded template with “You are a system assistant…” — accurate but not **useful** for daily chat.
- **Recommendation**: Replace with a 5–10 line **markdown summary** built deterministically from `key_evidence` (headings + first bullets), keep “view raw evidence” behind a debug flag or second turn.

### 7. Role and caution

- **Observation**: System text correctly tells the model not to invent scan results, but older **hard** refusal patterns trained into local models can still dominate.
- **Recommendation**: Keep the softened instruction (short useful reply + what’s missing); optionally add **one-shot** positive example in system prompt for “weak evidence” turns (low token cost).

### 8. Deprecated / stale context

- **Risk**: `workflow_rules.json` and session SQLite can surface **stale** last_scan paths; models may hallucinate bridges between stale and new facts.
- **Recommendation**: Stamp “retrieved_at” in evidence headers (where missing) and instruct model to prefer newest timestamp when conflicts appear.

## Suggested code changes (prioritized, small)

1. **`_format_evidence` caps** in `build_grounded_response`: lower `max_chars_per` for chat vs batch jobs (env-driven).
2. **No-LLM formatter**: new helper `format_evidence_reply_markdown(fused)` used instead of raw template passthrough.
3. **Worker health**: parallelize checks with `asyncio.wait_for` / thread pool + **global budget** (see fix plan).
4. **Tests**: extend `test_routing_policy.py` when adding new fast paths; keep `test_integration_flows.py` for insufficient and greeting invariants.
