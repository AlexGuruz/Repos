#!/usr/bin/env python3
"""
Test Full Workflow
=================
Apply new DDL migrations and test the complete workflow:
1. Apply DDL migrations (0011, 0012)
2. Seed test data (transactions, rules)
3. Run triage worker
4. Verify pending_txns and outbox events
5. Add a rule to match a pending item
6. Run replay worker
7. Verify promotion to active queue
"""

import os
import sys
import json
import psycopg2
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.triage.worker import triage_company_batch
from services.replay.worker import replay_after_promotion

def load_ddl_migration(conn, migration_file):
    """Load and execute a DDL migration file"""
    ddl_path = project_root / "db" / "ddl" / migration_file
    with open(ddl_path, 'r') as f:
        sql = f.read()
    
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    print(f"✓ Applied migration: {migration_file}")

def setup_test_data(conn, company_id="test-company"):
    """Seed test data for workflow testing"""
    with conn.cursor() as cur:
        # Insert test transactions
        test_txns = [
            ("txn-001", "2024-01-15 10:30:00+00", 2500, "STARBUCKS COFFEE", "batch-test-001"),
            ("txn-002", "2024-01-15 11:45:00+00", 1500, "WALMART GROCERIES", "batch-test-001"),
            ("txn-003", "2024-01-15 14:20:00+00", 5000, "UNKNOWN VENDOR XYZ", "batch-test-001"),
        ]
        
        for txn_uid, occurred_at, amount_cents, description_norm, batch_id in test_txns:
            cur.execute("""
                insert into app.transactions 
                (txn_uid, occurred_at, amount_cents, description_norm, last_seen_batch)
                values (%s, %s, %s, %s, %s)
                on conflict (txn_uid) do update set
                last_seen_batch = excluded.last_seen_batch,
                amount_cents = excluded.amount_cents,
                description_norm = excluded.description_norm
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
    print(f"✓ Seeded test data for company: {company_id}")

def verify_triage_results(conn, company_id, batch_id):
    """Verify triage worker results"""
    with conn.cursor() as cur:
        # Check pending_txns
        cur.execute("""
            select count(*) from app.pending_txns 
            where first_seen_batch = %s
        """, (batch_id,))
        pending_count = cur.fetchone()[0]
        
        # Check outbox events
        cur.execute("""
            select count(*) from control.outbox_events 
            where topic = 'pending.ready' and key = %s
        """, (company_id,))
        outbox_count = cur.fetchone()[0]
        
        # Check sort_queue (matched items)
        cur.execute("""
            select count(*) from app.sort_queue 
            where batch_id = %s and reason = 'feed.updated'
        """, (batch_id,))
        sorted_count = cur.fetchone()[0]
    
    print(f"✓ Triage results: {sorted_count} matched, {pending_count} pending, {outbox_count} outbox events")
    return pending_count, sorted_count

def add_matching_rule(conn, company_id, description_norm, target_header="New Category"):
    """Add a new rule to match a pending transaction"""
    with conn.cursor() as cur:
        # Get current rules
        cur.execute("""
            select payload from app.rules_active 
            where company_id = %s 
            order by version desc limit 1
        """, (company_id,))
        current_rules = cur.fetchone()[0]
        
        # Add new rule
        new_rule = {
            "source_norm": description_norm,
            "target_header": target_header,
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
    print(f"✓ Added rule for: {description_norm} → {target_header}")

def verify_replay_results(conn, company_id):
    """Verify replay worker results"""
    with conn.cursor() as cur:
        # Check resolved pending items
        cur.execute("""
            select count(*) from app.pending_txns 
            where status = 'resolved'
        """)
        resolved_count = cur.fetchone()[0]
        
        # Check new sort_queue entries
        cur.execute("""
            select count(*) from app.sort_queue 
            where reason = 'feed.updated' and batch_id = 'replay'
        """)
        replay_sorted_count = cur.fetchone()[0]
    
    print(f"✓ Replay results: {resolved_count} resolved, {replay_sorted_count} new sort queue entries")
    return resolved_count, replay_sorted_count

def main():
    """Run the full workflow test"""
    # Get database connection from environment
    pg_dsn = os.getenv('PG_DSN')
    if not pg_dsn:
        print("❌ Error: PG_DSN environment variable not set")
        sys.exit(1)
    
    company_id = "test-company"
    batch_id = "batch-test-001"
    
    print("🚀 Starting Full Workflow Test")
    print("=" * 50)
    
    try:
        # Connect to database
        conn = psycopg2.connect(pg_dsn)
        
        # Step 1: Apply DDL migrations
        print("\n📋 Step 1: Applying DDL migrations...")
        load_ddl_migration(conn, "0011_app_pending_txns.sql")
        load_ddl_migration(conn, "0012_control_sheet_posts.sql")
        
        # Step 2: Setup test data
        print("\n📊 Step 2: Setting up test data...")
        setup_test_data(conn, company_id)
        
        # Step 3: Run triage worker
        print("\n🔍 Step 3: Running triage worker...")
        triage_results = triage_company_batch(pg_dsn, company_id, batch_id)
        print(f"✓ Triage worker returned: {triage_results}")
        
        # Step 4: Verify triage results
        print("\n✅ Step 4: Verifying triage results...")
        pending_count, sorted_count = verify_triage_results(conn, company_id, batch_id)
        
        # Step 5: Add a rule to match a pending item
        print("\n📝 Step 5: Adding matching rule...")
        add_matching_rule(conn, company_id, "WALMART GROCERIES", "Groceries")
        
        # Step 6: Run replay worker
        print("\n🔄 Step 6: Running replay worker...")
        replay_results = replay_after_promotion(pg_dsn, company_id)
        print(f"✓ Replay worker returned: {replay_results}")
        
        # Step 7: Verify replay results
        print("\n✅ Step 7: Verifying replay results...")
        resolved_count, replay_sorted_count = verify_replay_results(conn, company_id)
        
        # Summary
        print("\n🎉 Workflow Test Summary")
        print("=" * 50)
        print(f"• Initial transactions: 3")
        print(f"• Matched by triage: {sorted_count}")
        print(f"• Sent to pending: {pending_count}")
        print(f"• Resolved by replay: {resolved_count}")
        print(f"• New sort queue entries: {replay_sorted_count}")
        
        if resolved_count > 0 and replay_sorted_count > 0:
            print("\n✅ SUCCESS: Full workflow working correctly!")
        else:
            print("\n❌ FAILURE: Replay did not work as expected")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n❌ Error during workflow test: {e}")
        sys.exit(1)
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()
