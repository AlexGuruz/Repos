import json
import subprocess
import time
from pathlib import Path

import pytest


def _dexec(container: str, *args: str, check: bool = True, capture_output: bool = True):
    return subprocess.run(
        ["docker", "exec", container, *args],
        check=check,
        capture_output=capture_output,
        text=True,
    )


@pytest.mark.integration
def test_sql_mover_smoke_watermark_and_outbox(tmp_path: Path):
    container = "kylo-pg-test-mover"
    try:
        # Start PG16
        subprocess.run(
            [
                "docker",
                "run",
                "--name",
                container,
                "-e",
                "POSTGRES_PASSWORD=kylo",
                "-d",
                "postgres:16",
            ],
            check=True,
        )

        # Wait briefly for startup
        time.sleep(5)

        # Create DBs
        _dexec(container, "createdb", "-U", "postgres", "kylo_global")
        _dexec(container, "createdb", "-U", "postgres", "kylo_company_a")
        _dexec(container, "createdb", "-U", "postgres", "kylo_company_b")

        repo_root = Path(__file__).resolve().parents[3]
        ddl_global = repo_root / "db" / "ddl" / "0002_core_intake_control.sql"
        ddl_helpers = repo_root / "db" / "ddl" / "0003_helpers.sql"
        ddl_company = repo_root / "db" / "ddl" / "company_0001_app.sql"
        fixtures = repo_root / "scaffold" / "tests" / "mover" / "fixtures.sql"

        # Copy DDLs + fixtures
        _dexec(container, "mkdir", "-p", "/ddl")
        subprocess.run(["docker", "cp", str(ddl_global), f"{container}:/ddl/0002.sql"], check=True)
        subprocess.run(["docker", "cp", str(ddl_helpers), f"{container}:/ddl/0003.sql"], check=True)
        subprocess.run(["docker", "cp", str(ddl_company), f"{container}:/ddl/company.sql"], check=True)
        subprocess.run(["docker", "cp", str(fixtures), f"{container}:/ddl/fixtures.sql"], check=True)

        # Apply DDLs
        _dexec(container, "psql", "-U", "postgres", "-d", "kylo_global", "-f", "/ddl/0002.sql")
        _dexec(container, "psql", "-U", "postgres", "-d", "kylo_global", "-f", "/ddl/0003.sql")
        _dexec(container, "psql", "-U", "postgres", "-d", "kylo_company_a", "-f", "/ddl/company.sql")
        _dexec(container, "psql", "-U", "postgres", "-d", "kylo_company_b", "-f", "/ddl/company.sql")

        # Seed fixtures (creates batch 1001, company feeds A/B = 0, two core txns for A)
        _dexec(container, "psql", "-U", "postgres", "-f", "/ddl/fixtures.sql")

        # Representative SQL-only mover for batch 1001
        # 1) Slice from global into temp table
        slice_sql = r"""
        BEGIN;
        CREATE TEMP TABLE tmp_slice AS
        SELECT company_id, txn_uid, posted_date, amount_cents, currency_code,
               description, counterparty_name, memo, category,
               source_stream_id, source_file_fingerprint, row_index_0based, hash_norm
        FROM core.transactions_unified
        WHERE ingest_batch_id = 1001;
        COMMIT;
        """
        _dexec(
            container,
            "psql",
            "-U",
            "postgres",
            "-d",
            "kylo_global",
            "-c",
            slice_sql,
        )

        # 2) Upsert into company A in single TX, enqueue, advance watermark in global, emit outbox
        upsert_a_sql = r"""
        BEGIN;
        -- Build a temp slice for company A directly in company DB
        CREATE TEMP TABLE tmp_a (
          txn_uid UUID,
          posted_date DATE,
          amount_cents INTEGER,
          currency_code TEXT,
          description TEXT,
          counterparty_name TEXT,
          memo TEXT,
          category TEXT,
          source_stream_id TEXT,
          source_file_fingerprint CHAR(64),
          row_index_0based INTEGER,
          hash_norm CHAR(64)
        ) ON COMMIT DROP;

        INSERT INTO tmp_a VALUES
          ('00000000-0000-0000-0000-00000000aaa1','2025-02-21',12345,'USD','Test Coffee 1',NULL,NULL,NULL,'cashpool',repeat('a',64),0,repeat('c',64)),
          ('00000000-0000-0000-0000-00000000aaa2','2025-02-22',-2500,'USD','Test Debit 2',NULL,NULL,NULL,'cashpool',repeat('a',64),1,repeat('d',64));

        -- Insert/Update app.transactions
        INSERT INTO app.transactions (
          txn_uid, posted_date, amount_cents, currency_code, description, counterparty_name, memo, category,
          source_stream_id, source_file_fingerprint, row_index_0based, hash_norm
        )
        SELECT
          txn_uid, posted_date, amount_cents, currency_code, description, counterparty_name, memo, category,
          source_stream_id, source_file_fingerprint, row_index_0based, hash_norm
        FROM tmp_a
        ON CONFLICT (txn_uid) DO UPDATE SET
          posted_date = EXCLUDED.posted_date,
          amount_cents = EXCLUDED.amount_cents,
          currency_code = EXCLUDED.currency_code,
          description = EXCLUDED.description,
          counterparty_name = EXCLUDED.counterparty_name,
          memo = EXCLUDED.memo,
          category = EXCLUDED.category,
          source_stream_id = EXCLUDED.source_stream_id,
          source_file_fingerprint = EXCLUDED.source_file_fingerprint,
          row_index_0based = EXCLUDED.row_index_0based,
          hash_norm = EXCLUDED.hash_norm
        WHERE app.transactions.hash_norm IS DISTINCT FROM EXCLUDED.hash_norm;

        -- Enqueue distinct txn_uids for feed.updated
        INSERT INTO app.sort_queue (txn_uid, reason)
        SELECT DISTINCT txn_uid, 'feed.updated' FROM tmp_a
        ON CONFLICT (txn_uid, reason) DO NOTHING;
        COMMIT;
        """
        _dexec(container, "psql", "-U", "postgres", "-d", "kylo_company_a", "-c", upsert_a_sql)

        # 3) Advance watermark for A if rows moved
        advance_sql = r"""
        UPDATE control.company_feeds
        SET last_batch_id = 1001, last_updated_at = now()
        WHERE company_id = 'company_a' AND last_batch_id < 1001;
        """
        _dexec(container, "psql", "-U", "postgres", "-d", "kylo_global", "-c", advance_sql)

        # 4) Emit outbox event for A (idempotent)
        outbox_payload = json.dumps({"company_id": "company_a", "ingest_batch_id": 1001})
        outbox_sql = f"""
        INSERT INTO control.outbox_events(topic, payload, event_key)
        VALUES('company.feed.updated', '{outbox_payload.replace("'", "''")}', 'feed.company_a.1001')
        ON CONFLICT DO NOTHING;
        """
        _dexec(container, "psql", "-U", "postgres", "-d", "kylo_global", "-c", outbox_sql)

        # 5) Do nothing for B (no rows in slice)

        # Assertions
        out_txns = _dexec(
            container,
            "psql",
            "-U",
            "postgres",
            "-d",
            "kylo_company_a",
            "-t",
            "-c",
            "SELECT count(*) FROM app.transactions;",
        )
        assert out_txns.stdout.strip().endswith("2")

        out_queue = _dexec(
            container,
            "psql",
            "-U",
            "postgres",
            "-d",
            "kylo_company_a",
            "-t",
            "-c",
            "SELECT count(*) FROM app.sort_queue WHERE reason='feed.updated';",
        )
        assert out_queue.stdout.strip().endswith("2")

        out_watermarks = _dexec(
            container,
            "psql",
            "-U",
            "postgres",
            "-d",
            "kylo_global",
            "-t",
            "-c",
            "SELECT company_id, last_batch_id FROM control.company_feeds ORDER BY company_id;",
        )
        txt = out_watermarks.stdout
        assert "company_a" in txt and "1001" in txt
        assert "company_b" in txt and " 0" in txt

        out_outbox = _dexec(
            container,
            "psql",
            "-U",
            "postgres",
            "-d",
            "kylo_global",
            "-t",
            "-c",
            "SELECT event_key FROM control.outbox_events WHERE event_key='feed.company_a.1001';",
        )
        assert out_outbox.stdout.strip().endswith("feed.company_a.1001")

    finally:
        subprocess.run(["docker", "rm", "-f", container], check=False)


