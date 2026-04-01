# GrowFlow inventory/sales data → database ingestion

Inventory and sales data from the **GrowFlow API** (order items: `findOrderItems`) is ingested into a **database** so you can query and analyze it without calling the API every time.

## What gets ingested

- **Order items** (sales line items): `sold_at`, `gross`, `cog`, `sku`, `category`, etc., keyed by GrowFlow `object_id` for dedupe.
- Stored in table **`growflow_order_items`** (SQLite or Postgres).

## Setup

### 1. Configure the database

In **`company_bi/config/sources.yaml`** under `database`:

- **SQLite (default):** No config needed. Uses `company_bi/db/growflow.db` (relative to repo root). To override:
  ```yaml
  database:
    path: "company_bi/db/growflow.db"   # or an absolute path
  ```
- **Postgres:** Set a connection string and run the DDL once:
  ```yaml
  database:
    dsn: "postgresql://user:pass@host:5432/dbname"
  ```
  Then run:
  ```bash
  psql $DSN -f company_bi/db/001_growflow_order_items_pg.sql
  ```

### 2. Run the ingest

From the **Growflow repo root**:

```bash
python -m company_bi.scripts.ingest_growflow_to_db
python -m company_bi.scripts.ingest_growflow_to_db --months 12
```

This fetches order items from the GrowFlow API (same window as the BI pipeline) and inserts/updates them in the DB. Re-running is safe (upsert by `object_id`).

## Using the data

- **Queries:** Point your SQL client or BI tool at the same DB. Table: `growflow_order_items`. Columns: `object_id`, `sold_at`, `year`, `month`, `day`, `date_str`, `gross`, `cog`, `sku`, `category`, `ingested_at`.
- **Pipeline:** Run the BI pipeline from the DB with **`--from-db`** (no API call for order items):
  ```bash
  python -m company_bi.run_pipeline --from-db
  python -m company_bi.run_pipeline --from-db --no-sheets
  ```
  The pipeline loads order items for the same month window as `--months` (default 24). If the DB is empty or not configured, it falls back to the API automatically.

## Schema and scripts

- **SQLite:** `company_bi/db/001_growflow_order_items.sql` (table created automatically on first ingest).
- **Postgres:** `company_bi/db/001_growflow_order_items_pg.sql` (run once by hand).
- **Ingest module:** `company_bi.lib.growflow_db` (`ingest_order_items`, `load_order_items_from_db`).

## Scheduling

Run the ingest script on a schedule (e.g. daily) so the DB stays updated. Use the same GrowFlow credentials as the BI pipeline (env `GROWFLOW_CREDENTIALS_PATH` or `sources.yaml` `growflow.default_credentials_path`).
