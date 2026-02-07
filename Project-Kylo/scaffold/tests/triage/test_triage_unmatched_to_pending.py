import os
import psycopg2
import pytest
from services.triage.worker import triage_company_batch

pytestmark = pytest.mark.integration

def test_triage_inserts_pending_and_outbox(pg_dsn, seed_company_db):
    # Arrange: seed app.transactions with one row and no active rules
    conn = psycopg2.connect(pg_dsn)
    with conn.cursor() as cur:
        cur.execute("insert into app.transactions (txn_uid, occurred_at, amount_cents, description_norm, last_seen_batch) values (%s, now(), %s, %s, %s)",
                    ("uid1", 1234, "atm load", "batch-x"))
    conn.commit(); conn.close()

    # Act
    out = triage_company_batch(pg_dsn, "CID", "batch-x")

    # Assert
    assert out["matched"] == 0 and out["unmatched"] == 1
    conn = psycopg2.connect(pg_dsn)
    with conn.cursor() as cur:
        cur.execute("select count(*) from app.pending_txns where txn_uid='uid1'")
        assert cur.fetchone()[0] == 1
    conn.close()
