"""
Database Storage Service
Handles efficient storage of CSV transactions with bulk operations
"""

import json
import logging
from io import StringIO
from typing import Dict, List, Optional

import psycopg2

log = logging.getLogger(__name__)


class StorageError(Exception):
    """Raised when database storage operations fail"""
    pass


def create_ingest_batch(db_conn, source: str = "petty_cash_csv") -> int:
    """Create a new ingest batch and return the batch ID"""
    with db_conn.cursor() as cur:
        cur.execute("""
            INSERT INTO control.ingest_batches (source, started_at)
            VALUES (%s, NOW())
            RETURNING batch_id
        """, (source,))
        batch_id = cur.fetchone()[0]
        db_conn.commit()
        return batch_id


def store_csv_transactions_batch(
    db_conn, 
    transactions: List[Dict], 
    batch_id: int,
    use_copy: bool = True
) -> Dict[str, int]:
    """
    Store CSV transactions efficiently using bulk operations
    
    Args:
        db_conn: Database connection
        transactions: List of transaction dictionaries
        batch_id: Ingest batch ID
        use_copy: Whether to use COPY for large batches
    
    Returns:
        Dictionary with storage results
    """
    if not transactions:
        return {
            "batch_id": batch_id,
            "transactions_stored": 0,
            "duplicates_skipped": 0,
            "errors": 0
        }
    
    original_count = len(transactions)
    stored_count = 0
    duplicates_skipped = 0
    errors = 0
    
    # Choose storage method based on batch size
    if use_copy and len(transactions) > 1000:
        stored_count, duplicates_skipped, errors = _store_with_copy(db_conn, transactions, batch_id)
    else:
        stored_count, duplicates_skipped, errors = _store_with_batch_insert(db_conn, transactions, batch_id)
    
    log.info(f"Storage complete: {stored_count} stored, {duplicates_skipped} duplicates, {errors} errors")
    
    return {
        "batch_id": batch_id,
        "transactions_stored": stored_count,
        "duplicates_skipped": duplicates_skipped,
        "errors": errors,
        "original_count": original_count
    }


def _store_with_copy(db_conn, transactions: List[Dict], batch_id: int) -> tuple:
    """Store transactions using PostgreSQL COPY for large batches"""
    stored_count = 0
    duplicates_skipped = 0
    errors = 0
    
    try:
        with db_conn.cursor() as cur:
            # Create temp table for bulk operations
            cur.execute("""
                CREATE TEMP TABLE temp_csv_transactions (
                    txn_uid UUID,
                    batch_id BIGINT,
                    company_id TEXT,
                    posted_date DATE,
                    amount_cents INTEGER,
                    description TEXT,
                    hash_norm CHAR(64),
                    business_hash CHAR(64),
                    row_index_0based INTEGER,
                    source_stream_id TEXT,
                    source_file_fingerprint CHAR(64),
                    raw_payload JSONB
                )
            """)
            
            # Prepare data for COPY
            data = StringIO()
            for txn in transactions:
                try:
                    # Convert transaction to tab-separated format
                    row_data = [
                        str(txn['txn_uid']),
                        str(batch_id),
                        txn['company_id'],
                        txn['posted_date'],
                        str(txn['amount_cents']),
                        txn['description'],
                        txn['hash_norm'],
                        txn.get('business_hash', ''),
                        str(txn['row_index_0based']),
                        txn['source_stream_id'],
                        txn['source_file_fingerprint'],
                        json.dumps(txn['raw_row'])
                    ]
                    data.write('\t'.join(str(field) for field in row_data) + '\n')
                except Exception as e:
                    log.warning(f"Error preparing transaction for COPY: {e}")
                    errors += 1
                    continue
            
            data.seek(0)
            
            # Use COPY for bulk insert to temp table
            cur.copy_from(data, 'temp_csv_transactions', sep='\t')
            
            # Insert from temp table with deduplication
            cur.execute("""
                INSERT INTO intake.raw_transactions (
                    ingest_id, ingest_batch_id, source_stream_id, company_id,
                    payload_json, fingerprint, business_hash, source_file_fingerprint, row_index_0based
                )
                SELECT 
                    txn_uid, batch_id, source_stream_id, company_id,
                    raw_payload, hash_norm, business_hash, source_file_fingerprint, row_index_0based
                FROM temp_csv_transactions
                ON CONFLICT (fingerprint) DO NOTHING
            """)
            
            stored_count = cur.rowcount
            
            # Insert into core.transactions_unified
            cur.execute("""
                INSERT INTO core.transactions_unified (
                    txn_uid, company_id, source_stream_id, posted_date,
                    amount_cents, description, hash_norm, source_file_fingerprint,
                    row_index_0based, ingest_batch_id
                )
                SELECT 
                    t.txn_uid, t.company_id, t.source_stream_id, t.posted_date,
                    t.amount_cents, t.description, t.hash_norm, t.source_file_fingerprint,
                    t.row_index_0based, t.batch_id
                FROM temp_csv_transactions t
                INNER JOIN intake.raw_transactions r ON r.fingerprint = t.hash_norm
                ON CONFLICT (source_stream_id, source_file_fingerprint, row_index_0based) 
                DO UPDATE SET
                    updated_at = NOW(),
                    hash_norm = EXCLUDED.hash_norm
                WHERE core.transactions_unified.hash_norm != EXCLUDED.hash_norm
            """)
            
            duplicates_skipped = len(transactions) - stored_count
            
    except Exception as e:
        log.error(f"Error in COPY storage: {e}")
        raise StorageError(f"COPY storage failed: {e}")
    
    return stored_count, duplicates_skipped, errors


def _store_with_batch_insert(db_conn, transactions: List[Dict], batch_id: int) -> tuple:
    """Store transactions using batch INSERT for smaller batches"""
    stored_count = 0
    duplicates_skipped = 0
    errors = 0
    
    try:
        with db_conn.cursor() as cur:
            # Prepare transaction data
            transaction_data = []
            for txn in transactions:
                try:
                    transaction_data.append((
                        txn['txn_uid'],
                        batch_id,
                        txn['company_id'],
                        txn['posted_date'],
                        txn['amount_cents'],
                        txn['description'],
                        txn['hash_norm'],
                        txn.get('business_hash'),
                        txn['row_index_0based'],
                        txn['source_stream_id'],
                        txn['source_file_fingerprint'],
                        json.dumps(txn['raw_row'])
                    ))
                except Exception as e:
                    log.warning(f"Error preparing transaction for batch insert: {e}")
                    errors += 1
                    continue
            
            if not transaction_data:
                return 0, 0, errors
            
            # Batch insert with deduplication
            cur.executemany("""
                INSERT INTO intake.raw_transactions (
                    ingest_id, ingest_batch_id, source_stream_id, company_id,
                    payload_json, fingerprint, business_hash, source_file_fingerprint, row_index_0based
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (fingerprint) DO NOTHING
            """, transaction_data)
            
            stored_count = cur.rowcount
            duplicates_skipped = len(transactions) - stored_count
            
            # Insert into core.transactions_unified for stored transactions
            if stored_count > 0:
                # Get the stored transactions
                stored_uuids = [txn[0] for txn in transaction_data[:stored_count]]
                
                cur.execute("""
                    INSERT INTO core.transactions_unified (
                        txn_uid, company_id, source_stream_id, posted_date,
                        amount_cents, description, hash_norm, source_file_fingerprint,
                        row_index_0based, ingest_batch_id
                    )
                    SELECT 
                        r.ingest_id, r.company_id, r.source_stream_id, 
                        (r.payload_json->>'posted_date')::DATE,
                        (r.payload_json->>'amount_cents')::INTEGER,
                        r.payload_json->>'description',
                        r.fingerprint, r.source_file_fingerprint, r.row_index_0based, r.ingest_batch_id
                    FROM intake.raw_transactions r
                    WHERE r.ingest_id = ANY(%s)
                    ON CONFLICT (source_stream_id, source_file_fingerprint, row_index_0based) 
                    DO UPDATE SET
                        updated_at = NOW(),
                        hash_norm = EXCLUDED.hash_norm
                    WHERE core.transactions_unified.hash_norm != EXCLUDED.hash_norm
                """, (stored_uuids,))
    
    except Exception as e:
        log.error(f"Error in batch insert storage: {e}")
        raise StorageError(f"Batch insert storage failed: {e}")
    
    return stored_count, duplicates_skipped, errors


def get_storage_stats(db_conn, batch_id: int) -> Dict:
    """Get storage statistics for a specific batch"""
    with db_conn.cursor() as cur:
        # Get raw transactions count
        cur.execute("""
            SELECT COUNT(*) FROM intake.raw_transactions 
            WHERE ingest_batch_id = %s
        """, (batch_id,))
        raw_count = cur.fetchone()[0]
        
        # Get unified transactions count
        cur.execute("""
            SELECT COUNT(*) FROM core.transactions_unified 
            WHERE ingest_batch_id = %s
        """, (batch_id,))
        unified_count = cur.fetchone()[0]
        
        # Get company distribution
        cur.execute("""
            SELECT company_id, COUNT(*) 
            FROM core.transactions_unified 
            WHERE ingest_batch_id = %s 
            GROUP BY company_id
        """, (batch_id,))
        company_distribution = dict(cur.fetchall())
        
        return {
            'batch_id': batch_id,
            'raw_transactions': raw_count,
            'unified_transactions': unified_count,
            'company_distribution': company_distribution
        }


def cleanup_temp_data(db_conn):
    """Clean up temporary data and optimize tables"""
    try:
        with db_conn.cursor() as cur:
            # Clean up any temp tables
            cur.execute("DROP TABLE IF EXISTS temp_csv_transactions")
            
            # Analyze tables for better query planning
            cur.execute("ANALYZE intake.raw_transactions")
            cur.execute("ANALYZE core.transactions_unified")
            
        log.info("Cleanup completed successfully")
        
    except Exception as e:
        log.warning(f"Cleanup failed: {e}")


def validate_storage_integrity(db_conn, batch_id: int) -> Dict:
    """Validate storage integrity for a batch"""
    with db_conn.cursor() as cur:
        # Check for orphaned records
        cur.execute("""
            SELECT COUNT(*) FROM intake.raw_transactions r
            LEFT JOIN core.transactions_unified u ON r.ingest_id = u.txn_uid
            WHERE r.ingest_batch_id = %s AND u.txn_uid IS NULL
        """, (batch_id,))
        orphaned_raw = cur.fetchone()[0]
        
        cur.execute("""
            SELECT COUNT(*) FROM core.transactions_unified u
            LEFT JOIN intake.raw_transactions r ON u.txn_uid = r.ingest_id
            WHERE u.ingest_batch_id = %s AND r.ingest_id IS NULL
        """, (batch_id,))
        orphaned_unified = cur.fetchone()[0]
        
        # Check for data consistency
        cur.execute("""
            SELECT COUNT(*) FROM intake.raw_transactions r
            INNER JOIN core.transactions_unified u ON r.ingest_id = u.txn_uid
            WHERE r.ingest_batch_id = %s 
                AND (r.company_id != u.company_id 
                     OR r.fingerprint != u.hash_norm)
        """, (batch_id,))
        inconsistent = cur.fetchone()[0]
        
        return {
            'batch_id': batch_id,
            'orphaned_raw_transactions': orphaned_raw,
            'orphaned_unified_transactions': orphaned_unified,
            'inconsistent_records': inconsistent,
            'integrity_ok': (orphaned_raw == 0 and orphaned_unified == 0 and inconsistent == 0)
        }
