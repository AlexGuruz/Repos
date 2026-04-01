# How categories work and how to set them yourself

## Where transactions come from

- Rows are read from the **Transactions** and **Bank** tabs (JGD master sheets, cleaned by Project-Kylo).
- Each row has a **Source** (description) column and an **Amount** column. Only **expenses** (amount &lt; 0) are categorized into labor, overhead, inventory, etc.

## How a transaction gets a category

1. The **Source** text is normalized to uppercase (`source_upper`).
2. The pipeline loads rules from **`config/categories.yaml`**.
3. For each expense row, rules are tried in order (longer patterns first). The **first** rule whose **pattern** appears **anywhere** in the description wins.
4. That rule sets **category** (e.g. `overhead`) and **subcategory** (e.g. `rent`). Amount is then summed into that category/subcategory by month.

So: **rent** = every expense whose Source/description contains one of the rent patterns (see below).

---

## Where you set the rules

**File:** `company_bi/config/categories.yaml`

**Structure:** Under each top-level key (`income`, `labor`, `inventory`, `overhead`), you list rules. Each rule has:

- **pattern:** Substring to find in the transaction description (case-insensitive). First match wins; longer patterns are tried first.
- **subcategory:** Name used in reports (e.g. `rent`, `utilities`). This is what appears as "Bill type" in the recurring bills report.
- **fixed:** (optional) `true` or `false` for overhead; used for fixed vs variable tagging.

---

## Current rules that feed into RENT

These are in `config/categories.yaml` under `overhead:`:

```yaml
  - pattern: "RENT"
    subcategory: rent
    fixed: true
  - pattern: "LEASE"
    subcategory: rent
    fixed: true
  - pattern: "PROPERTY PAYMENT"
    subcategory: rent
    fixed: true
```

So any expense whose **Source** contains "RENT", "LEASE", or "PROPERTY PAYMENT" is aggregated into the **rent** subcategory (and thus into the "rent" row in the recurring bills summary).

---

## How to change or add rules yourself

1. Open **`company_bi/config/categories.yaml`**.
2. Under **overhead:** (or labor/inventory as needed), add or edit entries.

**Add a new pattern for rent (e.g. your landlord or building name):**

```yaml
overhead:
  - pattern: "YOUR LANDLORD NAME"
    subcategory: rent
    fixed: true
  - pattern: "RENT"
    subcategory: rent
    fixed: true
  # ... rest of overhead rules
```

**Use a different subcategory name:** Change `subcategory:` to whatever you want (e.g. `rent` → `lease`). That name will appear in the recurring bills report. To keep "rent" as the label, keep `subcategory: rent` and only add/change **pattern** values.

**Remove a pattern:** Delete that rule block (the `- pattern: "..."` and its `subcategory:` and `fixed:` lines).

**Order:** More specific patterns should be listed before broader ones if both could match (e.g. "PROPERTY PAYMENT" before "PAYMENT"). The code sorts by pattern length (longest first), so longer patterns are tried first automatically.

---

## Quick reference: which config controls what

| You want to change…        | Edit in `config/categories.yaml` |
|---------------------------|-----------------------------------|
| What counts as rent       | `overhead:` → add/change/remove rules with `subcategory: rent` |
| What counts as utilities  | `overhead:` → rules with `subcategory: utilities` |
| What counts as insurance | `overhead:` → rules with `subcategory: insurance` |
| What counts as labor     | `labor:` section (patterns + subcategory) |
| What counts as inventory | `inventory:` section |

After saving the YAML, re-run the pipeline or `recurring_bills_summary` to see updated numbers; no code changes are required.
