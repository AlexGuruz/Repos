import os
import psycopg2
import pytest
import json
from datetime import datetime, timezone
from services.triage.worker import triage_company_batch

pytestmark = pytest.mark.integration

class TestTriageEdgeCases:
    """Test triage worker with edge cases and normalization quirks"""
    
    def test_empty_batch_handling(self, pg_dsn, seed_company_db):
        """Test triage with no transactions in batch"""
        # Act
        result = triage_company_batch(pg_dsn, "test-company", "empty-batch")
        
        # Assert
        assert result["matched"] == 0
        assert result["unmatched"] == 0
    
    def test_special_characters_in_descriptions(self, pg_dsn, seed_company_db):
        """Test handling of special characters in transaction descriptions"""
        conn = psycopg2.connect(pg_dsn)
        
        # Arrange: transactions with special characters
        special_txns = [
            ("txn-special-1", "2024-01-15 10:00:00+00", 1000, "CAFÉ & BISTRO", "batch-special"),
            ("txn-special-2", "2024-01-15 11:00:00+00", 2000, "MCDONALD'S®", "batch-special"),
            ("txn-special-3", "2024-01-15 12:00:00+00", 3000, "STORE #123 (24/7)", "batch-special"),
            ("txn-special-4", "2024-01-15 13:00:00+00", 4000, "GAS STATION & CONVENIENCE", "batch-special"),
        ]
        
        with conn.cursor() as cur:
            for txn_uid, occurred_at, amount_cents, description_norm, batch_id in special_txns:
                cur.execute("""
                    insert into app.transactions 
                    (txn_uid, occurred_at, amount_cents, description_norm, last_seen_batch)
                    values (%s, %s, %s, %s, %s)
                """, (txn_uid, occurred_at, amount_cents, description_norm, batch_id))
        conn.commit()
        conn.close()
        
        # Act
        result = triage_company_batch(pg_dsn, "test-company", "batch-special")
        
        # Assert
        assert result["matched"] == 0
        assert result["unmatched"] == 4
        
        # Verify all went to pending
        conn = psycopg2.connect(pg_dsn)
        with conn.cursor() as cur:
            cur.execute("select count(*) from app.pending_txns where first_seen_batch = 'batch-special'")
            assert cur.fetchone()[0] == 4
        conn.close()
    
    def test_case_sensitivity_matching(self, pg_dsn, seed_company_db):
        """Test that matching is case-sensitive"""
        conn = psycopg2.connect(pg_dsn)
        
        # Arrange: transaction with mixed case
        with conn.cursor() as cur:
            cur.execute("""
                insert into app.transactions 
                (txn_uid, occurred_at, amount_cents, description_norm, last_seen_batch)
                values (%s, %s, %s, %s, %s)
            """, ("txn-case", "2024-01-15 10:00:00+00", 1000, "StArBuCkS cOfFeE", "batch-case"))
            
            # Rule with different case
            rule = [{"source_norm": "STARBUCKS COFFEE", "target_header": "Coffee", "target_sheet": "Active"}]
            cur.execute("""
                insert into app.rules_active (company_id, version, payload, created_at)
                values (%s, 1, %s::jsonb, now())
            """, ("test-company", json.dumps(rule)))
        conn.commit()
        conn.close()
        
        # Act
        result = triage_company_batch(pg_dsn, "test-company", "batch-case")
        
        # Assert: should not match due to case difference
        assert result["matched"] == 0
        assert result["unmatched"] == 1
    
    def test_whitespace_handling(self, pg_dsn, seed_company_db):
        """Test handling of leading/trailing whitespace"""
        conn = psycopg2.connect(pg_dsn)
        
        # Arrange: transaction with extra whitespace
        with conn.cursor() as cur:
            cur.execute("""
                insert into app.transactions 
                (txn_uid, occurred_at, amount_cents, description_norm, last_seen_batch)
                values (%s, %s, %s, %s, %s)
            """, ("txn-whitespace", "2024-01-15 10:00:00+00", 1000, "  STARBUCKS COFFEE  ", "batch-whitespace"))
            
            # Rule with clean whitespace
            rule = [{"source_norm": "STARBUCKS COFFEE", "target_header": "Coffee", "target_sheet": "Active"}]
            cur.execute("""
                insert into app.rules_active (company_id, version, payload, created_at)
                values (%s, 1, %s::jsonb, now())
            """, ("test-company", json.dumps(rule)))
        conn.commit()
        conn.close()
        
        # Act
        result = triage_company_batch(pg_dsn, "test-company", "batch-whitespace")
        
        # Assert: should not match due to whitespace difference
        assert result["matched"] == 0
        assert result["unmatched"] == 1
    
    def test_duplicate_transaction_handling(self, pg_dsn, seed_company_db):
        """Test handling of duplicate transactions in same batch"""
        conn = psycopg2.connect(pg_dsn)
        
        # Arrange: same transaction twice in batch
        with conn.cursor() as cur:
            cur.execute("""
                insert into app.transactions 
                (txn_uid, occurred_at, amount_cents, description_norm, last_seen_batch)
                values (%s, %s, %s, %s, %s)
            """, ("txn-dupe", "2024-01-15 10:00:00+00", 1000, "DUPLICATE VENDOR", "batch-dupe"))
            
            # Insert same transaction again (should be ignored due to txn_uid constraint)
            cur.execute("""
                insert into app.transactions 
                (txn_uid, occurred_at, amount_cents, description_norm, last_seen_batch)
                values (%s, %s, %s, %s, %s)
                on conflict (txn_uid) do update set
                last_seen_batch = excluded.last_seen_batch
            """, ("txn-dupe", "2024-01-15 10:00:00+00", 1000, "DUPLICATE VENDOR", "batch-dupe"))
        conn.commit()
        conn.close()
        
        # Act
        result = triage_company_batch(pg_dsn, "test-company", "batch-dupe")
        
        # Assert: should only process once
        assert result["unmatched"] == 1
    
    def test_mixed_matching_scenarios(self, pg_dsn, seed_company_db):
        """Test mixed scenarios with some matches and some non-matches"""
        conn = psycopg2.connect(pg_dsn)
        
        # Arrange: mix of matching and non-matching transactions
        test_txns = [
            ("txn-match-1", "2024-01-15 10:00:00+00", 1000, "STARBUCKS COFFEE", "batch-mixed"),
            ("txn-match-2", "2024-01-15 11:00:00+00", 2000, "WALMART GROCERIES", "batch-mixed"),
            ("txn-nomatch-1", "2024-01-15 12:00:00+00", 3000, "UNKNOWN VENDOR", "batch-mixed"),
            ("txn-nomatch-2", "2024-01-15 13:00:00+00", 4000, "ANOTHER UNKNOWN", "batch-mixed"),
        ]
        
        with conn.cursor() as cur:
            for txn_uid, occurred_at, amount_cents, description_norm, batch_id in test_txns:
                cur.execute("""
                    insert into app.transactions 
                    (txn_uid, occurred_at, amount_cents, description_norm, last_seen_batch)
                    values (%s, %s, %s, %s, %s)
                """, (txn_uid, occurred_at, amount_cents, description_norm, batch_id))
            
            # Rules matching only some transactions
            rules = [
                {"source_norm": "STARBUCKS COFFEE", "target_header": "Coffee", "target_sheet": "Active"},
                {"source_norm": "WALMART GROCERIES", "target_header": "Groceries", "target_sheet": "Active"},
            ]
            cur.execute("""
                insert into app.rules_active (company_id, version, payload, created_at)
                values (%s, 1, %s::jsonb, now())
            """, ("test-company", json.dumps(rules)))
        conn.commit()
        conn.close()
        
        # Act
        result = triage_company_batch(pg_dsn, "test-company", "batch-mixed")
        
        # Assert
        assert result["matched"] == 2
        assert result["unmatched"] == 2
        
        # Verify sort_queue has matched items
        conn = psycopg2.connect(pg_dsn)
        with conn.cursor() as cur:
            cur.execute("select count(*) from app.sort_queue where batch_id = 'batch-mixed'")
            assert cur.fetchone()[0] == 2
        conn.close()
    
    def test_zero_amount_transactions(self, pg_dsn, seed_company_db):
        """Test handling of zero amount transactions"""
        conn = psycopg2.connect(pg_dsn)
        
        # Arrange: transaction with zero amount
        with conn.cursor() as cur:
            cur.execute("""
                insert into app.transactions 
                (txn_uid, occurred_at, amount_cents, description_norm, last_seen_batch)
                values (%s, %s, %s, %s, %s)
            """, ("txn-zero", "2024-01-15 10:00:00+00", 0, "ZERO AMOUNT VENDOR", "batch-zero"))
        conn.commit()
        conn.close()
        
        # Act
        result = triage_company_batch(pg_dsn, "test-company", "batch-zero")
        
        # Assert: should still be processed
        assert result["matched"] == 0
        assert result["unmatched"] == 1
        
        # Verify it went to pending
        conn = psycopg2.connect(pg_dsn)
        with conn.cursor() as cur:
            cur.execute("select amount_cents from app.pending_txns where txn_uid = 'txn-zero'")
            amount = cur.fetchone()[0]
            assert amount == 0
        conn.close()
    
    def test_very_long_descriptions(self, pg_dsn, seed_company_db):
        """Test handling of very long transaction descriptions"""
        conn = psycopg2.connect(pg_dsn)
        
        # Arrange: transaction with very long description
        long_desc = "A" * 1000  # Very long description
        with conn.cursor() as cur:
            cur.execute("""
                insert into app.transactions 
                (txn_uid, occurred_at, amount_cents, description_norm, last_seen_batch)
                values (%s, %s, %s, %s, %s)
            """, ("txn-long", "2024-01-15 10:00:00+00", 1000, long_desc, "batch-long"))
        conn.commit()
        conn.close()
        
        # Act
        result = triage_company_batch(pg_dsn, "test-company", "batch-long")
        
        # Assert: should handle long descriptions
        assert result["matched"] == 0
        assert result["unmatched"] == 1
        
        # Verify description was stored correctly
        conn = psycopg2.connect(pg_dsn)
        with conn.cursor() as cur:
            cur.execute("select description_norm from app.pending_txns where txn_uid = 'txn-long'")
            stored_desc = cur.fetchone()[0]
            assert stored_desc == long_desc
        conn.close()
    
    def test_null_rule_handling(self, pg_dsn, seed_company_db):
        """Test handling when rules payload is null or empty"""
        conn = psycopg2.connect(pg_dsn)
        
        # Arrange: transaction and null rules
        with conn.cursor() as cur:
            cur.execute("""
                insert into app.transactions 
                (txn_uid, company_id, occurred_at, amount_cents, description_norm, last_seen_batch)
                values (%s, %s, %s, %s, %s, %s)
            """, ("txn-null-rules", "test-company", "2024-01-15 10:00:00+00", 1000, "SOME VENDOR", "batch-null-rules"))
            
            # Insert null rules
            cur.execute("""
                insert into app.rules_active (company_id, version, payload, created_at)
                values (%s, 1, null, now())
            """, ("test-company",))
        conn.commit()
        conn.close()
        
        # Act
        result = triage_company_batch(pg_dsn, "test-company", "batch-null-rules")
        
        # Assert: should handle null rules gracefully
        assert result["matched"] == 0
        assert result["unmatched"] == 1
