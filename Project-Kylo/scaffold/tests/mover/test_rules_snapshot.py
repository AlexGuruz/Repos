import os
import socket
import subprocess
import time
from pathlib import Path

import pytest

from services.mover.models import BatchMoveRequest, CompanyScope
from services.mover.service import MoverService


def _wait_for_postgres(container: str, timeout_seconds: int = 45) -> None:
    deadline = time.time() + timeout_seconds
    last_output = ""
    while time.time() < deadline:
        probe = subprocess.run(
            ["docker", "exec", container, "pg_isready", "-U", "postgres"],
            capture_output=True,
            text=True,
            check=False,
        )
        if probe.returncode == 0:
            return
        last_output = (probe.stderr or probe.stdout).strip()
        time.sleep(1)
    raise RuntimeError(f"postgres did not become ready in {timeout_seconds}s: {last_output}")


@pytest.mark.integration
def test_rules_snapshot_swap_and_enqueue(tmp_path: Path):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        host_port = s.getsockname()[1]
    container = f"kylo-pg-test-rules-snapshot-{host_port}"
    try:
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
        _wait_for_postgres(container)

        subprocess.run(["docker", "exec", container, "createdb", "-U", "postgres", "kylo_global"], check=True)
        subprocess.run(["docker", "exec", container, "createdb", "-U", "postgres", "kylo_company_a"], check=True)

        repo_root = Path(__file__).resolve().parents[3]
        ddl_global = repo_root / "db" / "ddl" / "0002_core_intake_control.sql"
        ddl_helpers = repo_root / "db" / "ddl" / "0003_helpers.sql"
        ddl_rulesver = repo_root / "db" / "ddl" / "0004_control_rules_version.sql"
        ddl_company = repo_root / "db" / "ddl" / "company_0001_app.sql"
        fixtures_core = repo_root / "scaffold" / "tests" / "mover" / "fixtures.sql"

        fixtures_rules = tmp_path / "fixtures_rules.sql"
        fixtures_rules.write_text(
            """
            \\connect kylo_global
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

        subprocess.run(["docker", "exec", container, "mkdir", "-p", "/ddl"], check=True)
        for src, dst in [
            (ddl_global, "/ddl/0002.sql"),
            (ddl_helpers, "/ddl/0003.sql"),
            (ddl_rulesver, "/ddl/0004.sql"),
            (ddl_company, "/ddl/company.sql"),
            (fixtures_core, "/ddl/fixtures.sql"),
            (fixtures_rules, "/ddl/fixtures_rules.sql"),
        ]:
            subprocess.run(["docker", "cp", str(src), f"{container}:{dst}"], check=True)

        for sql_file, db in [
            ("/ddl/0002.sql", "kylo_global"),
            ("/ddl/0003.sql", "kylo_global"),
            ("/ddl/0004.sql", "kylo_global"),
            ("/ddl/fixtures.sql", None),
            ("/ddl/fixtures_rules.sql", None),
            ("/ddl/company.sql", "kylo_company_a"),
        ]:
            args = ["docker", "exec", container, "psql", "-U", "postgres"]
            if db:
                args += ["-d", db]
            args += ["-f", sql_file]
            subprocess.run(args, check=True)

        os.environ["KYLO_GLOBAL_DSN"] = f"postgresql://postgres:kylo@localhost:{host_port}/kylo_global"
        os.environ["KYLO_COMPANY_A_DSN"] = f"postgresql://postgres:kylo@localhost:{host_port}/kylo_company_a"

        svc = MoverService(os.environ["KYLO_GLOBAL_DSN"], lambda _: os.environ["KYLO_COMPANY_A_DSN"])
        resp = svc.move_batch(BatchMoveRequest(ingest_batch_id=1002, companies=[CompanyScope(company_id="company_a")]))
        assert not resp.errors

        out = subprocess.run(
            [
                "docker",
                "exec",
                container,
                "psql",
                "-U",
                "postgres",
                "-d",
                "kylo_company_a",
                "-t",
                "-c",
                "SELECT count(*) FROM app.rules_active;",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert out.stdout.strip().isdigit() and int(out.stdout.strip()) >= 1

        out = subprocess.run(
            [
                "docker",
                "exec",
                container,
                "psql",
                "-U",
                "postgres",
                "-d",
                "kylo_company_a",
                "-t",
                "-c",
                "SELECT count(*) FROM app.sort_queue WHERE reason='rules.updated';",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert out.stdout.strip().isdigit()

        out = subprocess.run(
            [
                "docker",
                "exec",
                container,
                "psql",
                "-U",
                "postgres",
                "-d",
                "kylo_global",
                "-t",
                "-c",
                "SELECT count(*) FROM control.outbox_events WHERE topic='rules.updated';",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert out.stdout.strip().endswith("1")

        out = subprocess.run(
            [
                "docker",
                "exec",
                container,
                "psql",
                "-U",
                "postgres",
                "-d",
                "kylo_global",
                "-t",
                "-c",
                "SELECT payload->>'checksum' FROM control.outbox_events WHERE topic='rules.updated' ORDER BY created_at DESC LIMIT 1;",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        chk = out.stdout.strip()
        assert chk.startswith("md5:"), f"unexpected checksum: {chk}"
    finally:
        subprocess.run(["docker", "rm", "-f", container], check=False)


