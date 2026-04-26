# Cartel infused preroll multipack — transfer and API identifiers

**Purpose:** Document how to recognize **Cartel 7×1.2g infused preroll multipacks** (total **8.4g**) in **Growflow Retail** data—especially **`findTransfers` → `Packages` → `Product`**—so future runs, audits, and scripts use the same rules.

**Canonical code:** `lib/cartel_7pk_names.py` (`matches_cartel_transfer_preroll_pack_signifiers`, `is_cartel_7pk_product_name`, `cartel_pack_line_kept_after_fetch`, `product_brand_name`).

---

## What to look for (canonical signifier)

Retail and transfers often show this product as a **brand line + product title + weight**, for example:

`Cartel Oil Co | Infused Pre-Roll Bundle + 8.4G`

In the **API**, the pipe (`|`) is usually **display-only**; payloads are split across fields:

| Signal | Where it appears | Notes |
|--------|------------------|--------|
| **Cartel Oil Co** | `Product.Brand.Name` and/or inside `Product.Name` | Regex: `\bcartel\s+oil\s+co\b` (case-insensitive). Legacy exact brand **`Cartel`** is still accepted for older rows. |
| **Infused Pre-Roll Bundle** | `Product.Name` | Name must contain **infused**, **bundle**, and **pre-roll** *or* **preroll** (order among tokens does not matter). |
| **8.4g weight** | `Product.Name` | Matches **`8.4g`**, **`8.4 G`**, **`8.4G`** (7 × 1.2g multipack). |

**Exclusions (not this SKU class):** lines matching **14pk** or **disposable** / **cartridge** carve-outs in `lib/cartel_7pk_names.py` (`EXC_7PK`, `FOURTEEN_PK`).

---

## Transfers (`findTransfers`)

- Transfer **packages** are `Packages { ... on Packages { OriginalQty Product { Name Brand { Name } ... } } }`.
- **Prefer** matching using **`Product.Brand.Name` + `Product.Name`** as above when both exist.
- **Known gap:** Some package rows arrive with **`Product: null`** (no `Name` / `Brand`). Those units **cannot** be proven to be this multipack from the transfer payload alone; scripts should treat them as **unassigned** and document the gap (see `scripts/transfer_sellout_by_brand_category.py` validation output).

**Script that applies this on transfers:** `PYTHONPATH=. python scripts/transfer_sellout_by_brand_category.py` — prints an **API validation** block and tags rows consistent with `lib/cartel_7pk_names.py`.

---

## Order lines (`findOrderItems`) and velocity scripts

The same signifiers apply to **sales velocity** and **7pk projections**. Because **`Product.Name`** may **omit** the word “cartel” while **`Product.Brand.Name`** is **Cartel Oil Co**, any filter must pass **brand + name** together where available.

- **Broad server fetch** (name regex only): `scripts/_cartel_preroll_velocity_budget.py` — `SERVER_REGEX` includes patterns for **Cartel** names and for **Infused Pre-Roll Bundle + 8.4g** without requiring “cartel” in `Product.Name`.
- **Client filter** after fetch: `cartel_pack_line_kept_after_fetch` keeps signifier rows and legacy `PACK_RE` matches on name or `brand + name` blob.
- **7pk line subsets:** `scripts/_cartel_7pk_sellout_projection.py`, `scripts/cartel_7pk_portfolio_projection.py`, `scripts/validate_cartel_7pk_projection.py` — call `is_cartel_7pk_product_name(..., brand_name=order_item_brand_name(n), ...)`.

---

## Package history (`findPackages`)

**First-receipt / intake scripts** use a `matchesRegex` on product name; pattern lives in `scripts/_cartel_7pk_first_receipt_sellout.py` as **`PKG_NAME_RE`** (includes the same **bundle + 8.4g** alternates alongside legacy **7pk** / **Cartel + 8.4g** patterns).

---

## Legacy identifiers (still supported)

For rows that **do not** use the full bundle wording, the codebase still treats these as Cartel multipack / 7pk when other checks pass:

- Explicit **`7pk`** in `Product.Name` (and not **14pk** / disposables).
- **`cartel` in name** + **8.4g** weight token (older naming).

Details: `is_cartel_7pk_product_name` in `lib/cartel_7pk_names.py`.

---

## Changelog

| Date | Change |
|------|--------|
| 2026-04-09 | Documented **Cartel Oil Co + Infused Pre-Roll Bundle + 8.4G** as the canonical transfer/sales identifier; linked implementation in `lib/cartel_7pk_names.py` and transfer/velocity scripts. |
