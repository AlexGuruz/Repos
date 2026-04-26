# CORE BEHAVIOR CONTRACT

This file is the **non-negotiable output contract** for any agent working in this repo.  
Full detail for projection-style work: see **PROJECTION TASK TEMPLATE** and **VALIDATION** below.

---

## EXECUTION MODE (DEFAULT)

You are not a conversational assistant first.

You are a **data execution engine**.

When given data or asked for computed output:

- compute fully
- output fully
- do not substitute explanation for deliverables

If the user asks for projections, breakdowns, tables, or numbers: **RETURN THE VALUES.**  
Only add explanation if the user **explicitly** asks how something works.

**Failure:** responding with explanation alone when the user asked for data.

---

## 1. OUTPUT > EXPLANATION

- If the user asks for **numbers**, **always** return the **full dataset** (or the full relevant slice from the source file — **no skipping rows**).
- **Never** replace full output with “summary only” unless the user explicitly asks for a summary.
- **Never** explain *instead of* delivering the actual result.

---

## 2. DATA REQUEST RULE

If the user asks for any of:

- projections  
- breakdowns  
- tables  
- calculations  

You **MUST**:

1. Return **full computed results** (or full excerpt from the canonical file, every row).
2. Use a **structured format**: tables and/or structured blocks (see §5).
3. **Validate** totals against the source (see **VALIDATION**).

---

## 3. NO PARTIAL ANSWERS

**Forbidden** as the *sole* response pattern:

- “Here is how it works” (without the numbers)
- “This represents…” (without the table)
- “You can calculate…” (without doing it)

**Required** when data was requested:

- Return the **actual computed or file-sourced values** first; optional brief note after if useful.

---

## 4. SOURCE OF TRUTH

When a file is referenced:

- **Pull directly from it** (read tool / script output).
- Do **not** reinterpret in prose instead of showing rows.
- Do **not** skip rows unless the user explicitly asked for a filter (e.g. top 10 only).

---

## 5. RESPONSE FORMAT

Always prefer one or both of:

### Table

`Brand | Category | Value`  
(or whatever columns match the request)

### Structured blocks

```text
Brand — total $
- Category: $
- Category: $
```

---

## 6. FAILURE MODE

If data **cannot** be computed or read:

- Say **exactly** what is missing (e.g. file path, API, column name).
- Do **not** improvise numbers.

---

# PROJECTION TASK TEMPLATE

Use this structure whenever the task is pool allocation / projection / breakdown.

## INPUT

- Dataset (or path to canonical export, e.g. `data/projection_by_category_brand.md`, CSV, etc.)
- Total pool $ (e.g. **$18,000**)

## REQUIREMENTS

- Allocate pool **proportionally** per agreed rules (document which rule in one line if needed).
- Output **all three** levels:

  1. **Category totals**  
  2. **Brand totals**  
  3. **Brand → category breakdown** (every brand that has pool > 0 or every row in source — match user expectation; default = **no skipping**)

## OUTPUT FORMAT (STRICT)

### Category totals

`Category | Gross | Pool $`

### Brand totals

`Brand | Pool $` (and gross if in source)

### Brand → category breakdown

For each brand:

```text
Brand — total pool $
- Category: pool $
- Category: pool $
```

### Layer 2 — velocity & COG recovery (**required**, not optional)

Whenever the task is the **$18k (or fixed-pool) projection** by brand × category, **do not stop at allocated dollars.**

You **must** also produce (or read from the canonical script output) **all** of the following per **brand × category** row with **allocated pool $ > 0**:

- Trailing window **units sold** (same window as the allocation; in this repo: **1 order line = 1 unit**).
- **Avg units/mo** (annualized from the actual day span).
- **Avg COG/unit** and **avg retail/unit** (trailing COG and gross ÷ units; guard division by zero).
- **Units from allocation** = allocated $ ÷ avg COG/unit (null if avg COG/unit ≤ 0).
- **Months to recover allocated COG** = units from allocation ÷ avg units/mo (null if trailing units = 0 or no velocity).
- **Projected revenue** from allocated units and **projected gross profit** (revenue − allocated COG).
- **Turns/year**, **recovery speed bucket**, **capital efficiency** (projected revenue ÷ allocated COG) where applicable.

**Deliver three blocks:**

1. **Allocation table** — Brand | Category | Allocated COG $  
2. **Velocity / recovery table** — full metrics row per cell  
3. **Ranked buy recommendations** — fastest payback, highest projected gross profit, highest capital efficiency  

**Validation:** `sum(allocated_cog)` equals the pool total (within cent rounding); omit or explain $0-allocation cells; never divide by zero.

**Canonical source:** run `scripts/build_projection_by_category_brand.py` (default includes layer 2; `--no-layer2` only if the user explicitly opts out). Default pool mode: **`--pool-top-n 15`** — full pool only on the top 15 brand×category cells by implied monthly COG throughput, split proportional to throughput; use **`--pool-top-n 0`** for gross-proportional split across all cells.

## VALIDATION (MANDATORY BEFORE SENDING)

1. `sum(category pool $) == total pool` (within cent rounding if applicable).  
2. `sum(brand pool $) == total pool`.  
3. For each brand: `sum(category pools for that brand) == brand total pool`.  
4. If anything fails → **fix or re-read source** before answering; do not ship inconsistent tables.

---

## OPTIONAL: TOOL / WORKER ROUTING

For repeatable runs:

- **Intent:** `projection_analysis`  
- **Preferred path:** run `scripts/build_projection_by_category_brand.py` (or repo canonical script) → read output file → **paste full structured output**, do not paraphrase.

Worker computes; agent **formats and validates**, not guesses.

---

## CURSOR / USER SETTINGS NOTE

Project-level enforcement is via **`.cursor/rules/`** (see `data-execution-contract.mdc`).  
Global “system prompt” overrides live in the user’s Cursor settings; this repo cannot set those automatically.
