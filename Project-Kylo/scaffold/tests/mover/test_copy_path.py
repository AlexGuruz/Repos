import os
import types

import pytest


class _FakeCopyCtx:
    def __init__(self):
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def write_row(self, row):
        self.rows.append(tuple(row))


class _FakeCursor:
    def __init__(self):
        self.executed = []
        self._next_fetch = (0, 0)
        self.copy_ctx = _FakeCopyCtx()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self.executed.append((sql, params))
        # After UPSERT_FROM_STAGE, make fetchone return affected/enqueued counts
        if isinstance(sql, str) and "SELECT\n  (SELECT COUNT(*) FROM upsert) AS affected_txns" in sql:
            # Will be handled by fetchone default
            pass

    def fetchone(self):
        return self._next_fetch

    # Minimal copy() protocol
    def copy(self, _):
        return self.copy_ctx


class _FakeConn:
    def __init__(self):
        self.autocommit = False
        self.cur = _FakeCursor()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def cursor(self):
        return self.cur


def _make_rows(n: int):
    rows = []
    for i in range(n):
        rows.append(
            (
                "company_x",  # company_id
                f"00000000-0000-0000-0000-0000000000{i:02d}",  # txn_uid
                "2025-01-01",  # posted_date
                100 + i,  # amount_cents
                "USD",  # currency_code
                "desc",  # description
                "cp",  # counterparty_name
                "memo",  # memo
                "cat",  # category
                "stream",  # source_stream_id
                "f" * 64,  # source_file_fingerprint
                i,  # row_index_0based
                "h" * 64,  # hash_norm
            )
        )
    return rows


def test_copy_path_triggered_with_low_threshold(monkeypatch, caplog):
    # Ensure threshold is small so copy path triggers for 2 rows
    monkeypatch.setenv("KYLO_MOVER_COPY_THRESHOLD", "1")
    # Reload module to re-read env
    if "services.mover.service" in list(globals().get("_loaded", {})):
        import importlib
        import services.mover.service as svc
        importlib.reload(svc)
    else:
        globals()["_loaded"] = {}

    from services.mover.service import _execute_upsert_and_enqueue, LARGE_SLICE_THRESHOLD, log

    fake_conn = _FakeConn()
    fake_conn.cur._next_fetch = (2, 2)
    rows = _make_rows(2)

    with caplog.at_level("INFO"):
        affected, enqueued = _execute_upsert_and_enqueue(fake_conn, rows)

    assert affected == 2 and enqueued == 2
    # Confirm copy path by presence of temp-stage DDL execution
    executed_sql = "\n".join(sql for (sql, _params) in fake_conn.cur.executed if isinstance(sql, str))
    assert "CREATE TEMP TABLE" in executed_sql, "Expected COPY path temp table creation not observed"

