import os
import socket
import subprocess
import time
from pathlib import Path

import psycopg
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


def _dexec(container: str, *args: str, check: bool = True):
    return subprocess.run(["docker", "exec", container, *args], check=check, text=True, capture_output=True)


@pytest.mark.integration
def test_rules_snapshot_swap_and_enqueue():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        host_port = s.getsockname()[1]
    container = f"kylo-pg-test-rules-{host_port}"

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

        _dexec(container, "createdb", "-U", "postgres", "kylo_global")
        _dexec(container, "createdb", "-U", "postgres", "kylo_company_a")
        _dexec(container, "createdb", "-U", "postgres", "kylo_company_b")

        repo_root = Path(__file__).resolve().parents[3]
        files_to_copy = [
            (repo_root / "db" / "ddl" / "0002_core_intake_control.sql", "/0002.sql"),
            (repo_root / "db" / "ddl" / "0003_helpers.sql", "/0003.sql"),
            (repo_root / "db" / "ddl" / "0004_control_rules_version.sql", "/0004.sql"),
            (repo_root / "db" / "ddl" / "company_0001_app.sql", "/company.sql"),
            (repo_root / "scaffold" / "tests" / "mover" / "fixtures.sql", "/fixtures.sql"),
            (repo_root / "scaffold" / "tests" / "mover" / "fixtures_rules.sql", "/fixtures_rules.sql"),
        ]
        for src, dst in files_to_copy:
            subprocess.run(["docker", "cp", str(src), f"{container}:{dst}"], check=True)

        _dexec(container, "psql", "-U", "postgres", "-d", "kylo_global", "-f", "/0002.sql")
        _dexec(container, "psql", "-U", "postgres", "-d", "kylo_global", "-f", "/0003.sql")
        _dexec(container, "psql", "-U", "postgres", "-d", "kylo_global", "-f", "/0004.sql")
        _dexec(container, "psql", "-U", "postgres", "-f", "/fixtures.sql")
        _dexec(container, "psql", "-U", "postgres", "-f", "/fixtures_rules.sql")
        _dexec(container, "psql", "-U", "postgres", "-d", "kylo_company_a", "-f", "/company.sql")
        _dexec(container, "psql", "-U", "postgres", "-d", "kylo_company_b", "-f", "/company.sql")

        global_dsn = f"postgresql://postgres:kylo@localhost:{host_port}/kylo_global"
        company_a_dsn = f"postgresql://postgres:kylo@localhost:{host_port}/kylo_company_a"
        company_b_dsn = f"postgresql://postgres:kylo@localhost:{host_port}/kylo_company_b"
        os.environ["KYLO_GLOBAL_DSN"] = global_dsn
        os.environ["KYLO_COMPANY_A_DSN"] = company_a_dsn
        os.environ["KYLO_COMPANY_B_DSN"] = company_b_dsn

        svc = MoverService(global_dsn, lambda cid: company_a_dsn if cid == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" else company_b_dsn)
        resp = svc.move_batch(BatchMoveRequest(ingest_batch_id=1002, companies=[CompanyScope(company_id="aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")]))
        assert not resp.errors

        with psycopg.connect(company_a_dsn) as c, c.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM app.rules_active;")
            assert cur.fetchone()[0] >= 2
            cur.execute("SELECT COUNT(*) FROM app.sort_queue WHERE reason='rules.updated';")
            assert cur.fetchone()[0] >= 1

        with psycopg.connect(global_dsn) as g, g.cursor() as gc:
            gc.execute("SELECT COUNT(*) FROM control.outbox_events WHERE topic='rules.updated' AND (payload->>'company_id')='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';")
            assert gc.fetchone()[0] >= 1
            gc.execute("SELECT payload->>'checksum' FROM control.outbox_events WHERE topic='rules.updated' AND (payload->>'company_id')='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa' ORDER BY created_at DESC LIMIT 1;")
            chk = gc.fetchone()[0]
            assert isinstance(chk, str) and chk.startswith("md5:")

    finally:
        subprocess.run(["docker", "rm", "-f", container], check=False)


