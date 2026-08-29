from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_csv_intake_module():
    module_path = Path(__file__).resolve().parents[2] / "bin" / "csv_intake.py"
    spec = importlib.util.spec_from_file_location("kylo_csv_intake_under_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeConn:
    def __init__(self):
        self.commits = 0
        self.closed = False

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


class _FakeProcessor:
    def __init__(self, *_args, **_kwargs):
        pass

    def parse_transactions(self):
        return [
            {
                "txn_uid": "11111111-1111-1111-1111-111111111111",
                "company_id": "NUGZ",
                "posted_date": "2025-01-01",
                "amount_cents": 1234,
                "description": "Test purchase",
            }
        ]

    def get_processing_stats(self):
        return {
            "unique_rows_processed": 1,
            "duplicate_rows_skipped": 0,
        }


class _FakeDedup:
    def __init__(self, _conn):
        pass

    def check_file_already_processed(self, _fingerprint):
        return False

    def process_with_deduplication(self, transactions, file_fingerprint, batch_id):
        return {
            "status": "completed",
            "batch_id": batch_id,
            "file_fingerprint": file_fingerprint,
            "unique_transactions": transactions,
        }

    def record_file_processing(self, *_args, **_kwargs):
        pass


def test_process_csv_intake_commits_successful_database_work(monkeypatch):
    csv_intake = _load_csv_intake_module()
    conn = _FakeConn()

    monkeypatch.setattr(csv_intake, "download_petty_cash_csv", lambda *_args, **_kwargs: "csv")
    monkeypatch.setattr(csv_intake, "validate_csv_content", lambda _content: True)
    monkeypatch.setattr(
        csv_intake,
        "get_csv_metadata",
        lambda _content: {
            "file_fingerprint": "fingerprint",
            "total_lines": 2,
            "non_empty_lines": 2,
            "file_size_bytes": 3,
        },
    )
    monkeypatch.setattr(csv_intake, "_copy_csv_to_configured_paths", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(csv_intake, "PettyCashCSVProcessor", _FakeProcessor)
    monkeypatch.setattr(csv_intake, "validate_transaction", lambda _txn: (True, []))
    monkeypatch.setattr(csv_intake, "create_db_connection", lambda _db_url: conn)
    monkeypatch.setattr(csv_intake, "DeduplicationWorkflow", _FakeDedup)
    monkeypatch.setattr(csv_intake, "create_ingest_batch", lambda _conn, _source: 42)
    monkeypatch.setattr(
        csv_intake,
        "store_csv_transactions_batch",
        lambda _conn, txns, batch_id: {
            "batch_id": batch_id,
            "transactions_stored": len(txns),
            "duplicates_skipped": 0,
            "errors": 0,
        },
    )
    monkeypatch.setattr(csv_intake, "cleanup_temp_data", lambda _conn: None)
    monkeypatch.setattr(csv_intake, "get_storage_stats", lambda _conn, batch_id: {"batch_id": batch_id})

    result = csv_intake.process_csv_intake("sheet", "service-account.json", "postgresql://db", dry_run=False)

    assert result["status"] == "completed"
    assert conn.commits == 1
    assert conn.closed is True
