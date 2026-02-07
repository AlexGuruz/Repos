import subprocess
import time
from pathlib import Path

import pytest


@pytest.mark.integration
def test_global_schemas_apply_and_batches(tmp_path: Path):
    # Preconditions: docker available
    container = "kylo-pg-test"
    try:
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
        # Wait a bit for PG to start
        time.sleep(5)

        def dexec(*args, check=True, capture_output=True):
            return subprocess.run(
                ["docker", "exec", container] + list(args),
                check=check,
                capture_output=capture_output,
                text=True,
            )

        # Create DBs inside container
        dexec("createdb", "-U", "postgres", "kylo_global")
        dexec("createdb", "-U", "postgres", "kylo_company_a")

        repo_root = Path(__file__).resolve().parents[2]
        ddl_global = repo_root / "db" / "ddl" / "0002_core_intake_control.sql"
        ddl_helpers = repo_root / "db" / "ddl" / "0003_helpers.sql"
        ddl_company = repo_root / "db" / "ddl" / "company_0001_app.sql"

        # Copy DDLs into container
        dexec("mkdir", "-p", "/ddl")
        subprocess.run(["docker", "cp", str(ddl_global), f"{container}:/ddl/0002.sql"], check=True)
        subprocess.run(["docker", "cp", str(ddl_helpers), f"{container}:/ddl/0003.sql"], check=True)
        subprocess.run(["docker", "cp", str(ddl_company), f"{container}:/ddl/company.sql"], check=True)

        # Apply DDLs using psql inside container
        dexec("psql", "-U", "postgres", "-d", "kylo_global", "-f", "/ddl/0002.sql")
        dexec("psql", "-U", "postgres", "-d", "kylo_global", "-f", "/ddl/0003.sql")
        dexec("psql", "-U", "postgres", "-d", "kylo_company_a", "-f", "/ddl/company.sql")

        # Smoke: insert a batch row and verify identity increments
        out = dexec(
            "psql",
            "-U",
            "postgres",
            "-d",
            "kylo_global",
            "-c",
            "INSERT INTO control.ingest_batches(source) VALUES('test') RETURNING batch_id;",
        )
        assert "batch_id" in out.stdout

        # Create company watermark row and ensure default is 0
        dexec(
            "psql",
            "-U",
            "postgres",
            "-d",
            "kylo_global",
            "-c",
            "INSERT INTO control.company_feeds(company_id) VALUES('company_a') ON CONFLICT DO NOTHING;",
        )
        out2 = dexec(
            "psql",
            "-U",
            "postgres",
            "-d",
            "kylo_global",
            "-c",
            "SELECT last_batch_id FROM control.company_feeds WHERE company_id='company_a';",
        )
        assert "0" in out2.stdout

        # Outbox table present and usable
        dexec(
            "psql",
            "-U",
            "postgres",
            "-d",
            "kylo_global",
            "-c",
            "INSERT INTO control.outbox_events(topic, payload, event_key) VALUES('company.feed.updated', '{\"company_id\":\"company_a\",\"ingest_batch_id\":1}', 'feed.company_a.1');",
        )
        # Unique event key enforced (should fail on duplicate)
        with pytest.raises(subprocess.CalledProcessError):
            dexec(
                "psql",
                "-U",
                "postgres",
                "-d",
                "kylo_global",
                "-c",
                "INSERT INTO control.outbox_events(topic, payload, event_key) VALUES('company.feed.updated', '{\"company_id\":\"company_a\",\"ingest_batch_id\":1}', 'feed.company_a.1');",
                check=True,
            )

    finally:
        # Cleanup container
        subprocess.run(["docker", "rm", "-f", container], check=False)


