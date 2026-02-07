import os
import psycopg2
import pytest
import json
from datetime import datetime, timezone
from services.triage.worker import triage_company_batch
from services.replay.worker import replay_after_promotion

pytestmark = pytest.mark.integration

class TestFullWorkflowIntegration:
    """Integration test for the complete workflow loop"""
    
    def test_complete_workflow_loop(self, pg_dsn, seed_company_db):
        """
        Test the complete workflow:
        1. Insert sample raw transactions
        2. Run triage worker
        3. Verify pending_txns and outbox events
        4. Add a rule to match a pending item
        5. Run replay worker
        6. Verify promotion to active queue
        """
        company_id = "test-company"
        batch_id = "batch-integration-test"
        
        # Step 1: Insert sample raw transactions
        conn = psycopg2.connect(pg_dsn)
        test_txns = [
            ("txn-int-001", "2024-01-15 10:30:00+00", 2500, "STARBUCKS COFFEE", batch_id),
            ("txn-int-002", "2024-01-15 11:45:00+00", 1500, "WALMART GROCERIES", batch_id),
            ("txn-int-003", "2024-01-15 14:20:00+00", 5000, "UNKNOWN VENDOR XYZ", batch_id),
            ("txn-int-004", "2024-01-15 16:10:00+00", 3000, "ANOTHER UNKNOWN", batch_id),
        ]
        
        with conn.cursor() as cur:
            for txn_uid, occurred_at, amount_cents, description_norm, batch_id in test_txns:
                cur.execute("""
                    insert into app.transactions 
                    (txn_uid, occurred_at, amount_cents, description_norm, last_seen_batch)
                    values (%s, %s, %s, %s, %s)
                """, (txn_uid, occurred_at, amount_cents, description_norm, batch_id))
            
            # Insert initial rules (only matching one transaction)
            initial_rules = [
                {
                    "source_norm": "STARBUCKS COFFEE",
                    "target_header": "Coffee & Dining",
                    "target_sheet": "Active"
                }
            ]
            cur.execute("""
                insert into app.rules_active (company_id, version, payload, created_at)
                values (%s, 1, %s::jsonb, now())
            """, (company_id, json.dumps(initial_rules)))
        conn.commit()
        conn.close()
        
        # Step 2: Run triage worker
        triage_results = triage_company_batch(pg_dsn, company_id, batch_id)
        
        # Verify triage results
        assert triage_results["matched"] == 1  # STARBUCKS COFFEE
        assert triage_results["unmatched"] == 3  # WALMART, UNKNOWN VENDOR, ANOTHER UNKNOWN
        
        # Step 3: Verify pending_txns and outbox events
        conn = psycopg2.connect(pg_dsn)
        with conn.cursor() as cur:
            # Check pending_txns
            cur.execute("""
                select count(*) from app.pending_txns 
                where first_seen_batch = %s and status = 'open'
            """, (batch_id,))
            pending_count = cur.fetchone()[0]
            assert pending_count == 3
            
            # Check outbox events
            cur.execute("""
                select count(*) from control.outbox_events 
                where topic = 'pending.ready' and key = %s
            """, (company_id,))
            outbox_count = cur.fetchone()[0]
            assert outbox_count == 1
            
            # Check sort_queue (matched items)
            cur.execute("""
                select count(*) from app.sort_queue 
                where batch_id = %s and reason = 'feed.updated'
            """, (batch_id,))
            sorted_count = cur.fetchone()[0]
            assert sorted_count == 1
            
            # Verify specific pending items
            cur.execute("""
                select description_norm from app.pending_txns 
                where first_seen_batch = %s and status = 'open'
                order by description_norm
            """, (batch_id,))
            pending_descriptions = [row[0] for row in cur.fetchall()]
            expected_pending = ["ANOTHER UNKNOWN", "UNKNOWN VENDOR XYZ", "WALMART GROCERIES"]
            assert pending_descriptions == expected_pending
        conn.close()
        
        # Step 4: Add a rule to match a pending item
        conn = psycopg2.connect(pg_dsn)
        with conn.cursor() as cur:
            # Get current rules
            cur.execute("""
                select payload from app.rules_active 
                where company_id = %s 
                order by version desc limit 1
            """, (company_id,))
            current_rules = cur.fetchone()[0]
            
            # Add new rule for WALMART GROCERIES
            new_rule = {
                "source_norm": "WALMART GROCERIES",
                "target_header": "Groceries",
                "target_sheet": "Active"
            }
            current_rules.append(new_rule)
            
            # Insert new version
            cur.execute("""
                insert into app.rules_active (company_id, version, payload, created_at)
                select %s, version + 1, %s::jsonb, now()
                from app.rules_active 
                where company_id = %s 
                order by version desc limit 1
            """, (company_id, json.dumps(current_rules), company_id))
        conn.commit()
        conn.close()
        
        # Step 5: Run replay worker
        replay_results = replay_after_promotion(pg_dsn, company_id)
        
        # Verify replay results
        assert replay_results["resolved"] == 1  # WALMART GROCERIES should be resolved
        
        # Step 6: Verify promotion to active queue
        conn = psycopg2.connect(pg_dsn)
        with conn.cursor() as cur:
            # Check that WALMART GROCERIES is now resolved
            cur.execute("""
                select status from app.pending_txns 
                where description_norm = 'WALMART GROCERIES'
            """)
            status = cur.fetchone()[0]
            assert status == 'resolved'
            
            # Check that other pending items are still open
            cur.execute("""
                select count(*) from app.pending_txns 
                where status = 'open'
            """)
            still_open_count = cur.fetchone()[0]
            assert still_open_count == 2  # ANOTHER UNKNOWN, UNKNOWN VENDOR XYZ
            
            # Check new sort_queue entries from replay
            cur.execute("""
                select count(*) from app.sort_queue 
                where reason = 'feed.updated' and batch_id = 'replay'
            """)
            replay_sorted_count = cur.fetchone()[0]
            assert replay_sorted_count == 1
            
            # Verify the specific transaction was queued
            cur.execute("""
                select txn_uid from app.sort_queue 
                where reason = 'feed.updated' and batch_id = 'replay'
            """)
            queued_txn = cur.fetchone()[0]
            assert queued_txn == 'txn-int-002'  # WALMART GROCERIES transaction
        conn.close()
    
    def test_replay_idempotency(self, pg_dsn, seed_company_db):
        """Test that replay worker is idempotent - safe to run multiple times"""
        company_id = "test-company-idempotent"
        batch_id = "batch-idempotent"
        
        # Setup: one transaction (no rule yet) -> triage creates pending -> then rule -> replay resolves
        conn = psycopg2.connect(pg_dsn)
        with conn.cursor() as cur:
            # Insert transaction
            cur.execute("""
                insert into app.transactions 
                (txn_uid, company_id, occurred_at, amount_cents, description_norm, last_seen_batch)
                values (%s, %s, %s, %s, %s, %s)
            """, ("txn-idem", company_id, "2024-01-15 10:00:00+00", 1000, "TEST VENDOR", batch_id))
        conn.commit()
        conn.close()
        
        # Run triage to create pending item
        triage_company_batch(pg_dsn, company_id, batch_id)

        # Insert rule after pending exists
        conn = psycopg2.connect(pg_dsn)
        with conn.cursor() as cur:
            rule = [{"source_norm": "TEST VENDOR", "target_header": "Test", "target_sheet": "Active"}]
            cur.execute("""
                insert into app.rules_active (company_id, version, payload, created_at)
                values (%s, 1, %s::jsonb, now())
            """, (company_id, json.dumps(rule)))
        conn.commit()
        conn.close()
        
        # Run replay multiple times
        result1 = replay_after_promotion(pg_dsn, company_id)
        result2 = replay_after_promotion(pg_dsn, company_id)
        result3 = replay_after_promotion(pg_dsn, company_id)
        
        # Verify only first run resolved items
        assert result1["resolved"] == 1
        assert result2["resolved"] == 0
        assert result3["resolved"] == 0
        
        # Verify no duplicate sort_queue entries
        conn = psycopg2.connect(pg_dsn)
        with conn.cursor() as cur:
            cur.execute("""
                select count(*) from app.sort_queue 
                where reason = 'feed.updated' and batch_id = 'replay'
            """)
            sort_queue_count = cur.fetchone()[0]
            assert sort_queue_count == 1  # Only one entry, not three
        conn.close()
    
    def test_multiple_companies_isolation(self, pg_dsn, seed_company_db):
        """Test that triage and replay work correctly with multiple companies"""
        company_a = "company-a"
        company_b = "company-b"
        batch_id = "batch-multi-company"
        
        # Setup transactions for both companies
        conn = psycopg2.connect(pg_dsn)
        with conn.cursor() as cur:
            # Company A transactions
            cur.execute("""
                insert into app.transactions 
                (txn_uid, company_id, occurred_at, amount_cents, description_norm, last_seen_batch)
                values (%s, %s, %s, %s, %s, %s)
            """, ("txn-a-1", company_a, "2024-01-15 10:00:00+00", 1000, "VENDOR A", batch_id))
            
            # Company B transactions
            cur.execute("""
                insert into app.transactions 
                (txn_uid, company_id, occurred_at, amount_cents, description_norm, last_seen_batch)
                values (%s, %s, %s, %s, %s, %s)
            """, ("txn-b-1", company_b, "2024-01-15 11:00:00+00", 2000, "VENDOR B", batch_id))
            
            # Rules for Company A only
            rule_a = [{"source_norm": "VENDOR A", "target_header": "Category A", "target_sheet": "Active"}]
            cur.execute("""
                insert into app.rules_active (company_id, version, payload, created_at)
                values (%s, 1, %s::jsonb, now())
            """, (company_a, json.dumps(rule_a)))
        conn.commit()
        conn.close()
        
        # Run triage for both companies
        result_a = triage_company_batch(pg_dsn, company_a, batch_id)
        result_b = triage_company_batch(pg_dsn, company_b, batch_id)
        
        # Verify Company A has match, Company B doesn't
        assert result_a["matched"] == 1
        assert result_a["unmatched"] == 0
        assert result_b["matched"] == 0
        assert result_b["unmatched"] == 1
        
        # Verify outbox events are company-specific
        conn = psycopg2.connect(pg_dsn)
        with conn.cursor() as cur:
            cur.execute("""
                select key, count(*) from control.outbox_events 
                where topic = 'pending.ready'
                group by key
            """)
            outbox_by_company = dict(cur.fetchall())
            assert outbox_by_company.get(company_a, 0) == 0  # Company A has no pending
            assert outbox_by_company.get(company_b, 0) == 1  # Company B has pending
        conn.close()
    
    def test_batch_signature_deduplication(self, pg_dsn, seed_company_db):
        """Test that batch signatures prevent duplicate sheet posts"""
        company_id = "test-company-dedup"
        batch_id = "batch-dedup"
        
        # Setup test data
        conn = psycopg2.connect(pg_dsn)
        with conn.cursor() as cur:
            cur.execute("""
                insert into app.transactions 
                (txn_uid, company_id, occurred_at, amount_cents, description_norm, last_seen_batch)
                values (%s, %s, %s, %s, %s, %s)
            """, ("txn-dedup", company_id, "2024-01-15 10:00:00+00", 1000, "TEST VENDOR", batch_id))
        conn.commit()
        conn.close()
        
        # Run triage twice (simulating duplicate processing)
        result1 = triage_company_batch(pg_dsn, company_id, batch_id)
        result2 = triage_company_batch(pg_dsn, company_id, batch_id)
        
        # Verify same results both times
        assert result1 == result2
        
        # Verify no duplicate pending entries
        conn = psycopg2.connect(pg_dsn)
        with conn.cursor() as cur:
            cur.execute("""
                select count(*) from app.pending_txns 
                where first_seen_batch = %s
            """, (batch_id,))
            pending_count = cur.fetchone()[0]
            assert pending_count == 1  # Only one entry, not two
        conn.close()
