# Email Backfill Dry-Run Report

- Generated at: `2026-03-19 22:44:06Z`
- Days window: `120`
- Mode: `dry-run (imap)`
- Limit: `50`
- Processed: `50`
- AI used: `0`
- Worker used: `0`

## Key Counts (Phase 1 dry-run)

- Permits: `27`
- Driver Credentials / Documents: `2`
- MYDOT: `13`
- PROGRESSIVE COMMERCIAL INSURANCE: `1`
- Needs Review: `7`
- Proposed archive count: `41`

## Summary by category

- permits: 27
- mydot: 13
- uncategorized: 7
- driver_document: 2
- progressive_insurance: 1

## Unique senders by final category (quick accuracy check)

_One line per distinct sender (or From header) that landed in each category._

### `permits` (1 unique)

- team@pilotcarloads.com

### `mydot` (1 unique)

- mydotd@info.la.gov

### `uncategorized` (3 unique)

- do-not-reply@meritrustcu.org
- sarah@pdffiller.com
- service@paypal.com

### `driver_document` (2 unique)

- deals@email.bestwesternrewards.com
- support@mktg.subarucommunications.com

### `progressive_insurance` (1 unique)

- progressivecommercial@e.progressive.com

## Summary by confidence band

- high: 41
- medium: 2
- low: 7

## Archive proposals (proposed outcomes)

- archive_proposed_count: 41

## Needs Review details

- Needs Review count (broad): 7

## Emails routed to Needs Review (low-confidence only samples)

- `D5.21.13825.EEE3CB96@ccg13mail03` | service@paypal.com | Your PayPal account features are temporarily blocked
- `0E.B6.13790.BF75CB96@ccg14mail04` | service@paypal.com | Stay logged in on this trusted device
- `89.B0.13825.DFA5CB96@ccg13mail03` | service@paypal.com | You added a new address
- `17739517527861.1.36973.5913958220@pdffiller.com` | sarah@pdffiller.com | 🔗 Share. 🖍️Annotate. 💬 Collaborate.
- `CE.19.14875.97D5CB96@ccg14mail02` | service@paypal.com | Your PayPal verification code
- `43.EC.14875.60E5CB96@ccg14mail02` | service@paypal.com | Login from a new device
- `491385310.229155965.1773956095918@sjmktmail-batch1j.marketo.org` | do-not-reply@meritrustcu.org | 📢 Meritrust Member Scholarship Applications Are Now Open

## Emails routed to Needs Review (sample: first 200)

- `D5.21.13825.EEE3CB96@ccg13mail03` | paypal.com | Your PayPal account features are temporarily blocked | deterministic=uncategorized | conf=0.25
- `0E.B6.13790.BF75CB96@ccg14mail04` | paypal.com | Stay logged in on this trusted device | deterministic=uncategorized | conf=0.25
- `89.B0.13825.DFA5CB96@ccg13mail03` | paypal.com | You added a new address | deterministic=uncategorized | conf=0.25
- `17739517527861.1.36973.5913958220@pdffiller.com` | pdffiller.com | 🔗 Share. 🖍️Annotate. 💬 Collaborate. | deterministic=uncategorized | conf=0.25
- `CE.19.14875.97D5CB96@ccg14mail02` | paypal.com | Your PayPal verification code | deterministic=uncategorized | conf=0.25
- `43.EC.14875.60E5CB96@ccg14mail02` | paypal.com | Login from a new device | deterministic=uncategorized | conf=0.25
- `491385310.229155965.1773956095918@sjmktmail-batch1j.marketo.org` | meritrustcu.org | 📢 Meritrust Member Scholarship Applications Are Now Open | deterministic=uncategorized | conf=0.25

## Top unmatched senders/domains (Needs Review, deterministic uncategorized)

- paypal.com: 5
- meritrustcu.org: 1
- pdffiller.com: 1

## Proposed new driver child labels (dry-run report-only)

_No new driver child label proposals._

## Audit log artifact

- JSONL: `E:\Repos\ai-lab\logs\email_sorter\backfill_imap_dryrun_1773960246.jsonl`

