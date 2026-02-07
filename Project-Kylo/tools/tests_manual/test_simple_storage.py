#!/usr/bin/env python3
"""
Simple Database Storage Test
"""

import subprocess
import json
import uuid

def test_simple_storage():
    """Test simple database storage"""
    print("🗄️ Testing Simple Database Storage...")
    
    try:
        # Create a test batch
        result = subprocess.run([
            'docker', 'exec', 'kylo-pg', 'psql', '-U', 'postgres', '-d', 'kylo_global',
            '-c', """
            INSERT INTO control.ingest_batches (source, started_at)
            VALUES ('test_simple', NOW())
            RETURNING batch_id;
            """
        ], capture_output=True, text=True, check=True)
        
        batch_id = int(result.stdout.strip().split('\n')[2])
        print(f"✅ Created batch: {batch_id}")
        
        # Create a simple test transaction
        txn_uid = str(uuid.uuid4())
        hash_norm = "a" * 64  # 64 character hash
        file_fingerprint = "b" * 64  # 64 character fingerprint
        
        # Insert into core.transactions_unified
        result = subprocess.run([
            'docker', 'exec', 'kylo-pg', 'psql', '-U', 'postgres', '-d', 'kylo_global',
            '-c', f"""
            INSERT INTO core.transactions_unified (
                txn_uid, company_id, source_stream_id, posted_date,
                amount_cents, description, hash_norm, source_file_fingerprint,
                row_index_0based, ingest_batch_id
            ) VALUES (
                '{txn_uid}', 'TEST', 'test_stream', '2025-01-15',
                1000, 'Test Transaction', '{hash_norm}', '{file_fingerprint}',
                1, {batch_id}
            );
            """
        ], capture_output=True, text=True, check=True)
        
        print("✅ Inserted test transaction")
        
        # Verify it was inserted
        result = subprocess.run([
            'docker', 'exec', 'kylo-pg', 'psql', '-U', 'postgres', '-d', 'kylo_global',
            '-c', f"SELECT COUNT(*) FROM core.transactions_unified WHERE txn_uid = '{txn_uid}';"
        ], capture_output=True, text=True, check=True)
        
        count = int(result.stdout.strip().split('\n')[2])
        if count == 1:
            print("✅ Transaction verified in database")
            return True
        else:
            print(f"❌ Transaction not found (count: {count})")
            return False
            
    except Exception as e:
        print(f"❌ Simple storage test failed: {e}")
        return False

if __name__ == "__main__":
    test_simple_storage()
