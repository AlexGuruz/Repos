import os
import sys
from pathlib import Path
import json
import pytest
import psycopg2

# Ensure repo root on sys.path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

# Default DSNs for local docker-postgres; can be overridden via env
os.environ.setdefault("KYLO_GLOBAL_DSN",    "postgresql://postgres:kylo@localhost:5432/kylo_global")
os.environ.setdefault("KYLO_COMPANY_A_DSN", "postgresql://postgres:kylo@localhost:5432/kylo_company_a")
os.environ.setdefault("KYLO_COMPANY_B_DSN", "postgresql://postgres:kylo@localhost:5432/kylo_company_b")



# ================= Additional test fixtures for DB-backed tests =================

@pytest.fixture(scope="session")
def pg_dsn() -> str:
    """Return a Postgres DSN for tests.

    Prefer explicit KYLO_TEST_DSN; else use docker compose mapped port 5433.
    """
    return os.getenv("KYLO_TEST_DSN", "postgresql://postgres:kylo@localhost:5433/postgres")


@pytest.fixture()
def seed_company_db(pg_dsn: str):
    """Create minimal schemas/tables used by triage/replay tests and clean between tests.

    This seeds a single logical company context inside schemas `app` and `control`.
    """
    conn = psycopg2.connect(pg_dsn)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            # Schemas
            cur.execute("""
                CREATE SCHEMA IF NOT EXISTS app;
                CREATE SCHEMA IF NOT EXISTS control;
            """)

            # Recreate tables each test to keep schema consistent with expectations.
            cur.execute(
                """
                DROP TABLE IF EXISTS control.outbox_events CASCADE;
                DROP TABLE IF EXISTS control.triage_metrics CASCADE;
                DROP TABLE IF EXISTS control.sheet_posts CASCADE;
                DROP TABLE IF EXISTS app.sort_queue CASCADE;
                DROP TABLE IF EXISTS app.pending_txns CASCADE;
                DROP TABLE IF EXISTS app.transactions CASCADE;
                DROP TABLE IF EXISTS app.rules_active CASCADE;
                """
            )

            # control tables
            cur.execute("""
                CREATE TABLE IF NOT EXISTS control.outbox_events (
                    id SERIAL PRIMARY KEY,
                    topic TEXT NOT NULL,
                    key   TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS control.triage_metrics (
                    id SERIAL PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    batch_id   TEXT,
                    operation  TEXT NOT NULL,
                    matched_count   INTEGER NOT NULL DEFAULT 0,
                    unmatched_count INTEGER NOT NULL DEFAULT 0,
                    resolved_count  INTEGER NOT NULL DEFAULT 0,
                    total_time_ms   INTEGER,
                    load_time_ms    INTEGER,
                    match_time_ms   INTEGER,
                    update_time_ms  INTEGER,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS control.sheet_posts (
                    id SERIAL PRIMARY KEY,
                    company_id TEXT NOT NULL,
                    tab_name   TEXT NOT NULL,
                    batch_signature TEXT NOT NULL,
                    row_count  INTEGER NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)
            cur.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS sheet_posts_company_batch_sig_uniq
                ON control.sheet_posts (company_id, batch_signature);
            """)

            # app tables
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app.transactions (
                    txn_uid TEXT PRIMARY KEY,
                    company_id TEXT,
                    occurred_at TIMESTAMPTZ,
                    amount_cents INTEGER,
                    description_norm TEXT,
                    last_seen_batch TEXT
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app.pending_txns (
                    txn_uid TEXT PRIMARY KEY,
                    company_id TEXT,
                    first_seen_batch TEXT,
                    last_seen_batch  TEXT,
                    occurred_at TIMESTAMPTZ,
                    description_norm TEXT,
                    amount_cents INTEGER,
                    row_checksum TEXT,
                    status TEXT NOT NULL DEFAULT 'open',
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app.sort_queue (
                    id SERIAL PRIMARY KEY,
                    reason TEXT NOT NULL,
                    txn_uid TEXT NOT NULL,
                    company_id TEXT,
                    queued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    batch_id TEXT,
                    UNIQUE (reason, txn_uid)
                );
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS app.rules_active (
                    company_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    payload JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    applied_at TIMESTAMPTZ,
                    PRIMARY KEY (company_id, version)
                );
            """)

        conn.commit()
        yield
    finally:
        try:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE app.sort_queue, app.pending_txns, app.transactions, app.rules_active RESTART IDENTITY CASCADE;")
                cur.execute("TRUNCATE control.outbox_events, control.triage_metrics, control.sheet_posts RESTART IDENTITY CASCADE;")
            conn.commit()
        except Exception:
            pass
        conn.close()

