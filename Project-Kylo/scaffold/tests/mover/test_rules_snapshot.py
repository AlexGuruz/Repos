import os
import socket
import subprocess
import time
from pathlib import Path

import pytest

from services.mover.models import BatchMoveRequest, CompanyScope
from services.mover.service import MoverService


@pytest.mark.integration
def test_rules_snapshot_swap_and_enqueue(tmp_path: Path):
    # choose unique container name per run
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        host_port = s.getsockname()[1]
    container = f"kylo-pg-test-rules-snapshot-{host_port}"
    try:
        subprocess.run([
            "docker", "run", "--name", container, "-p", f"{host_port}:5432",
            "-e", "POSTGRES_PASSWORD=kylo", "-d", "postgres:16"
        ], check=True)
        time.sleep(5)

        # Create DBs
        subprocess.run(["docker","exec",container,"createdb","-U","postgres","kylo_global"], check=True)
        subprocess.run(["docker","exec",container,"createdb","-U","postgres","kylo_company_a"], check=True)

        repo_root = Path(__file__).resolve().parents[3]
        ddl_global = repo_root / "db" / "ddl" / "0002_core_intake_control.sql"
        ddl_helpers = repo_root / "db" / "ddl" / "0003_helpers.sql"
        ddl_rulesver = repo_root / "db" / "ddl" / "0004_control_rules_version.sql"
        ddl_company = repo_root / "db" / "ddl" / "company_0001_app.sql"
        fixtures_core = repo_root / "scaffold" / "tests" / "mover" / "fixtures.sql"

        # Create a rules activation fixture dynamically
        fixtures_rules = tmp_path / "fixtures_rules.sql"
        fixtures_rules.write_text(
            """
            \connect kylo_global
            CREATE TABLE IF NOT EXISTS control.rules_activations (
              company_id text PRIMARY KEY,
              activate_at_batch bigint NOT NULL,
              snapshot jsonb NOT NULL
            );
            INSERT INTO control.rules_activations(company_id, activate_at_batch, snapshot)
            VALUES ('company_a', 1002, '[{"rule_id": "11111111-1111-1111-1111-111111111111", "rule_json": {"pattern": "*coffee*", "target_sheet": "Cash", "target_header": "Notes"}}]')
            ON CONFLICT (company_id) DO UPDATE SET activate_at_batch=EXCLUDED.activate_at_batch, snapshot=EXCLUDED.snapshot;
            """
        )

        # Copy files
        subprocess.run(["docker","exec",container,"mkdir","-p","/ddl"], check=True)
        for src, dst in [
            (ddl_global, "/ddl/0002.sql"),
            (ddl_helpers, "/ddl/0003.sql"),
            (ddl_rulesver, "/ddl/0004.sql"),
            (ddl_company, "/ddl/company.sql"),
            (fixtures_core, "/ddl/fixtures.sql"),
            (fixtures_rules, "/ddl/fixtures_rules.sql"),
        ]:
            subprocess.run(["docker","cp", str(src), f"{container}:{dst}"], check=True)

        # Apply DDL + fixtures
        for f, db in [
            ("/ddl/0002.sql", "kylo_global"),
            ("/ddl/0003.sql", "kylo_global"),
            ("/ddl/0004.sql", "kylo_global"),
            ("/ddl/fixtures.sql", None),
            ("/ddl/fixtures_rules.sql", None),
            ("/ddl/company.sql", "kylo_company_a"),
        ]:
            args = ["docker","exec",container,"psql","-U","postgres"]
            if db:
                args += ["-d", db]
            args += ["-f", f]
            subprocess.run(args, check=True)

        # DSNs
        os.environ["KYLO_GLOBAL_DSN"] = f"postgresql://postgres:kylo@localhost:{host_port}/kylo_global"
        os.environ["KYLO_COMPANY_A_DSN"] = f"postgresql://postgres:kylo@localhost:{host_port}/kylo_company_a"

        svc = MoverService(os.environ["KYLO_GLOBAL_DSN"], lambda _: os.environ["KYLO_COMPANY_A_DSN"])
        # Move 1002 (should activate)
        resp = svc.move_batch(BatchMoveRequest(ingest_batch_id=1002, companies=[CompanyScope(company_id="company_a")]))
        assert not resp.errors

        # Validate snapshot applied
        out = subprocess.run([
            "docker","exec",container,"psql","-U","postgres","-d","kylo_company_a","-t","-c",
            "SELECT count(*) FROM app.rules_active;"
        ], capture_output=True, text=True, check=True)
        assert out.stdout.strip().isdigit() and int(out.stdout.strip()) >= 1

        # Validate enqueue
        out = subprocess.run([
            "docker","exec",container,"psql","-U","postgres","-d","kylo_company_a","-t","-c",
            "SELECT count(*) FROM app.sort_queue WHERE reason='rules.updated';"
        ], capture_output=True, text=True, check=True)
        assert out.stdout.strip().isdigit()

        # Validate outbox rules.updated exists (from bump)
        out = subprocess.run([
            "docker","exec",container,"psql","-U","postgres","-d","kylo_global","-t","-c",
            "SELECT count(*) FROM control.outbox_events WHERE topic='rules.updated';"
        ], capture_output=True, text=True, check=True)
        assert out.stdout.strip().endswith("1")
        # Validate checksum present and shaped as md5:*
        out = subprocess.run([
            "docker","exec",container,"psql","-U","postgres","-d","kylo_global","-t","-c",
            "SELECT payload->>'checksum' FROM control.outbox_events WHERE topic='rules.updated' ORDER BY created_at DESC LIMIT 1;"
        ], capture_output=True, text=True, check=True)
        chk = out.stdout.strip()
        assert chk.startswith("md5:"), f"unexpected checksum: {chk}"
    finally:
        subprocess.run(["docker","rm","-f",container], check=False)

import os
import socket
import subprocess
import time

import psycopg
import pytest

from services.mover.models import BatchMoveRequest, CompanyScope
from services.mover.service import MoverService


@pytest.mark.integration
def test_rules_snapshot_swap_and_enqueue():
    # unique container name per run
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    container = f"kylo-pg-test-rules-{port}"
    # Choose a random local port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    try:
        subprocess.run([
            "docker", "run", "--name", container,
            "-p", f"{port}:5432",
            "-e", "POSTGRES_PASSWORD=kylo",
            "-d", "postgres:16"
        ], check=True)
        time.sleep(5)

        def dexec(*args, check=True):
            return subprocess.run(["docker", "exec", container, *args], check=check, text=True, capture_output=True)

        # DBs and DDL
        dexec("createdb", "-U", "postgres", "kylo_global")
        dexec("createdb", "-U", "postgres", "kylo_company_a")
        dexec("createdb", "-U", "postgres", "kylo_company_b")

        # Push DDL and fixtures
        repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        subprocess.run(["docker", "cp", os.path.join(repo, "db", "ddl", "0002_core_intake_control.sql"), f"{container}:/0002.sql"], check=True)
        subprocess.run(["docker", "cp", os.path.join(repo, "db", "ddl", "0003_helpers.sql"), f"{container}:/0003.sql"], check=True)
        subprocess.run(["docker", "cp", os.path.join(repo, "db", "ddl", "company_0001_app.sql"), f"{container}:/company.sql"], check=True)
        subprocess.run(["docker", "cp", os.path.join(repo, "scaffold", "tests", "mover", "fixtures.sql"), f"{container}:/fixtures.sql"], check=True)
        subprocess.run(["docker", "cp", os.path.join(repo, "scaffold", "tests", "mover", "fixtures_rules.sql"), f"{container}:/fixtures_rules.sql"], check=True)

        dexec("psql", "-U", "postgres", "-d", "kylo_global", "-f", "/0002.sql")
        dexec("psql", "-U", "postgres", "-d", "kylo_global", "-f", "/0003.sql")
        dexec("psql", "-U", "postgres", "-f", "/fixtures.sql")
        dexec("psql", "-U", "postgres", "-f", "/fixtures_rules.sql")
        dexec("psql", "-U", "postgres", "-d", "kylo_company_a", "-f", "/company.sql")
        dexec("psql", "-U", "postgres", "-d", "kylo_company_b", "-f", "/company.sql")

        # DSNs
        GLOBAL_DSN = f"postgresql://postgres:kylo@localhost:{port}/kylo_global"
        COMPANY_A_DSN = f"postgresql://postgres:kylo@localhost:{port}/kylo_company_a"
        COMPANY_B_DSN = f"postgresql://postgres:kylo@localhost:{port}/kylo_company_b"

        svc = MoverService(GLOBAL_DSN, lambda cid: COMPANY_A_DSN if cid == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" else COMPANY_B_DSN)
        # Batch 1002 triggers rules activation for company_a
        resp = svc.move_batch(BatchMoveRequest(ingest_batch_id=1002, companies=[CompanyScope(company_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")]))
        assert not resp.errors

        # Check company rules snapshot and enqueue
        with psycopg.connect(COMPANY_A_DSN) as c, c.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM app.rules_active;")
            assert cur.fetchone()[0] >= 2
            cur.execute("SELECT COUNT(*) FROM app.sort_queue WHERE reason='rules.updated';")
            assert cur.fetchone()[0] >= 1

        # Outbox rules.updated present
        with psycopg.connect(GLOBAL_DSN) as g, g.cursor() as gc:
            gc.execute("SELECT COUNT(*) FROM control.outbox_events WHERE topic='rules.updated' AND (payload->>'company_id')='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';")
            assert gc.fetchone()[0] >= 1
            gc.execute("SELECT payload->>'checksum' FROM control.outbox_events WHERE topic='rules.updated' AND (payload->>'company_id')='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' ORDER BY created_at DESC LIMIT 1;")
            chk = gc.fetchone()[0]
            assert isinstance(chk, str) and chk.startswith('md5:')

    finally:
        subprocess.run(["docker", "rm", "-f", container], check=False)


