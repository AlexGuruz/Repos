import json
import os
import socket
import subprocess
import time
from pathlib import Path

import pytest
from services.mover.models import BatchMoveRequest, CompanyScope
from services.mover.service import MoverService


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
        # Pick an available host port for Postgres to avoid conflicts
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            host_port = s.getsockname()[1]
        # Start PG16
        subprocess.run(
            [
                "docker",
                "run",
                "--name",
                container,
                "-p",
                f"{host_port}:5432",
                "-e",
                "POSTGRES_PASSWORD=kylo",
                "-d",
                "postgres:16",
            ],
            check=True,
        )

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

        # Apply DDLs and seed fixtures
        _dexec(container, "psql", "-U", "postgres", "-d", "kylo_global", "-f", "/ddl/0002.sql")
        _dexec(container, "psql", "-U", "postgres", "-d", "kylo_global", "-f", "/ddl/0003.sql")
        _dexec(container, "psql", "-U", "postgres", "-f", "/ddl/fixtures.sql")
        _dexec(container, "psql", "-U", "postgres", "-d", "kylo_company_a", "-f", "/ddl/company.sql")
        _dexec(container, "psql", "-U", "postgres", "-d", "kylo_company_b", "-f", "/ddl/company.sql")

        # Verify fixtures: expect 2 rows in global slice for batch 1001 and company_a
        out_global_cnt = _dexec(
            container,
            "psql",
            "-U",
            "postgres",
            "-d",
            "kylo_global",
            "-t",
            "-c",
            "SELECT count(*) FROM core.transactions_unified WHERE ingest_batch_id=1001 AND company_id='company_a';",
        )
        assert out_global_cnt.stdout.strip().endswith("2")

        # Invoke service wrapper that runs the proven SQL
        # Point DSNs to the dynamically mapped host port
        os.environ["KYLO_GLOBAL_DSN"] = f"postgresql://postgres:kylo@localhost:{host_port}/kylo_global"
        os.environ["KYLO_COMPANY_A_DSN"] = f"postgresql://postgres:kylo@localhost:{host_port}/kylo_company_a"
        os.environ["KYLO_COMPANY_B_DSN"] = f"postgresql://postgres:kylo@localhost:{host_port}/kylo_company_b"

        global_dsn = os.environ["KYLO_GLOBAL_DSN"]
        def resolver(cid: str) -> str:
            return {
                "company_a": os.environ.get("KYLO_COMPANY_A_DSN", "postgresql://postgres:kylo@localhost:5432/kylo_company_a"),
                "company_b": os.environ.get("KYLO_COMPANY_B_DSN", "postgresql://postgres:kylo@localhost:5432/kylo_company_b"),
            }[cid]

        svc = MoverService(global_dsn, resolver)
        resp = svc.move_batch(BatchMoveRequest(ingest_batch_id=1001, companies=[CompanyScope(company_id="company_a"), CompanyScope(company_id="company_b")]))
        assert not resp.errors

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


