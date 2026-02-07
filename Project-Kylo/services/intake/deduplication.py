"""
Deduplication Workflow Service
Implements multi-layer deduplication for CSV intake processing
"""

import logging
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher

log = logging.getLogger(__name__)


class DeduplicationWorkflow:
    """Multi-layer deduplication workflow for CSV intake"""
    
    def __init__(self, db_conn):
        self.db_conn = db_conn
    
    def check_file_already_processed(self, file_fingerprint: str) -> bool:
        """Check if CSV file has already been processed"""
        with self.db_conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM control.file_processing_log 
                WHERE file_fingerprint = %s
            """, (file_fingerprint,))
            count = cur.fetchone()[0]
            return count > 0
    
    def record_file_processing(self, file_fingerprint: str, batch_id: int, row_count: int, status: str = 'completed'):
        """Record that a file has been processed"""
        with self.db_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO control.file_processing_log (
                    file_fingerprint, batch_id, processed_at, row_count, status
                ) VALUES (%s, %s, NOW(), %s, %s)
                ON CONFLICT (file_fingerprint) DO UPDATE SET
                    processed_at = NOW(),
                    row_count = EXCLUDED.row_count,
                    status = EXCLUDED.status
            """, (file_fingerprint, batch_id, row_count, status))
    
    def check_content_duplicates(self, transactions: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Check for content-level duplicates (identical transactions)
        
        Returns:
            Tuple of (unique_transactions, duplicate_transactions)
        """
        unique_transactions = []
        duplicate_transactions = []
        
        with self.db_conn.cursor() as cur:
            for txn in transactions:
                # Check if this exact content hash already exists
                cur.execute("""
                    SELECT COUNT(*) FROM intake.raw_transactions 
                    WHERE fingerprint = %s
                """, (txn['hash_norm'],))
                
                if cur.fetchone()[0] > 0:
                    duplicate_transactions.append(txn)
                    log.debug(f"Content duplicate found for transaction {txn['txn_uid']}")
                else:
                    unique_transactions.append(txn)
        
        return unique_transactions, duplicate_transactions
    
    def check_business_duplicates(self, transactions: List[Dict], similarity_threshold: float = 0.8) -> List[Dict]:
        """
        Check for business-level duplicates (same day, amount, similar description)
        
        Args:
            transactions: List of transactions to check
            similarity_threshold: Minimum similarity score (0.0 to 1.0)
        
        Returns:
            List of business duplicate records
        """
        business_duplicates = []
        
        with self.db_conn.cursor() as cur:
            for txn in transactions:
                # Find existing transactions with same date, amount, and company
                cur.execute("""
                    SELECT 
                        txn_uid, description, posted_date, amount_cents
                    FROM core.transactions_unified
                    WHERE company_id = %s 
                        AND posted_date = %s 
                        AND amount_cents = %s
                        AND ABS(EXTRACT(EPOCH FROM (NOW() - created_at))) < 86400  -- Within 24 hours
                """, (txn['company_id'], txn['posted_date'], txn['amount_cents']))
                
                potential_duplicates = cur.fetchall()
                
                # Check description similarity
                for dup in potential_duplicates:
                    existing_txn_uid, existing_description, posted_date, amount_cents = dup
                    
                    similarity = self._calculate_description_similarity(
                        txn['description'], 
                        existing_description
                    )
                    
                    if similarity > similarity_threshold:
                        business_duplicate = {
                            'txn_uid': txn['txn_uid'],
                            'existing_txn_uid': existing_txn_uid,
                            'similarity': similarity,
                            'description': txn['description'],
                            'existing_description': existing_description,
                            'posted_date': posted_date,
                            'amount_cents': amount_cents,
                            'company_id': txn['company_id']
                        }
                        business_duplicates.append(business_duplicate)
                        
                        log.info(f"Business duplicate found: {txn['txn_uid']} vs {existing_txn_uid} (similarity: {similarity:.3f})")
        
        return business_duplicates
    
    def _calculate_description_similarity(self, desc1: str, desc2: str) -> float:
        """Calculate similarity between two descriptions"""
        # Normalize descriptions
        norm1 = self._normalize_description(desc1)
        norm2 = self._normalize_description(desc2)
        
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def _normalize_description(self, description: str) -> str:
        """Normalize description for similarity comparison"""
        import re
        
        # Convert to lowercase and trim
        normalized = description.lower().strip()
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove common punctuation
        normalized = re.sub(r'[^\w\s]', '', normalized)
        
        return normalized
    
    def record_deduplication_metrics(self, batch_id: int, dedup_type: str, original_count: int, final_count: int):
        """Record deduplication metrics"""
        duplicates_skipped = original_count - final_count
        
        with self.db_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO control.deduplication_log (
                    batch_id, dedup_type, original_count, final_count, duplicates_skipped
                ) VALUES (%s, %s, %s, %s, %s)
            """, (batch_id, dedup_type, original_count, final_count, duplicates_skipped))
    
    def record_business_duplicates(self, batch_id: int, business_duplicates: List[Dict]):
        """Record business-level duplicates for review"""
        if not business_duplicates:
            return
        
        with self.db_conn.cursor() as cur:
            for dup in business_duplicates:
                cur.execute("""
                    INSERT INTO control.business_duplicates (
                        batch_id, company_id, txn_uid, existing_txn_uid, similarity,
                        posted_date, amount_cents, description, existing_description
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    batch_id,
                    dup['company_id'],
                    dup['txn_uid'],
                    dup['existing_txn_uid'],
                    dup['similarity'],
                    dup['posted_date'],
                    dup['amount_cents'],
                    dup['description'],
                    dup['existing_description']
                ))
    
    def record_deduplication_summary(self, batch_id: int, file_fingerprint: str, summary: Dict):
        """Record comprehensive deduplication summary"""
        with self.db_conn.cursor() as cur:
            cur.execute("""
                INSERT INTO control.deduplication_summary (
                    batch_id, file_fingerprint, original_parsed, 
                    business_duplicates_found, final_stored, total_skipped
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                batch_id,
                file_fingerprint,
                summary.get('original_parsed', 0),
                summary.get('business_duplicates_found', 0),
                summary.get('final_stored', 0),
                summary.get('total_skipped', 0)
            ))
    
    def process_with_deduplication(self, transactions: List[Dict], file_fingerprint: str, batch_id: int) -> Dict:
        """
        Process transactions with comprehensive deduplication
        
        Args:
            transactions: List of parsed transactions
            file_fingerprint: File fingerprint for tracking
            batch_id: Batch ID for this processing run
        
        Returns:
            Dictionary with deduplication results
        """
        original_count = len(transactions)
        log.info(f"Starting deduplication for {original_count} transactions")
        
        # 1. File-level deduplication (already checked before calling this)
        if self.check_file_already_processed(file_fingerprint):
            return {
                "status": "skipped",
                "reason": "file_already_processed",
                "file_fingerprint": file_fingerprint,
                "original_count": original_count,
                "final_count": 0,
                "duplicates_skipped": original_count
            }
        
        # 2. Content-level deduplication
        unique_transactions, content_duplicates = self.check_content_duplicates(transactions)
        self.record_deduplication_metrics(batch_id, 'content', original_count, len(unique_transactions))
        
        log.info(f"Content deduplication: {len(content_duplicates)} duplicates found")
        
        # 3. Business-level deduplication
        business_duplicates = self.check_business_duplicates(unique_transactions)
        self.record_business_duplicates(batch_id, business_duplicates)
        
        log.info(f"Business deduplication: {len(business_duplicates)} potential duplicates found")
        
        # 4. Record summary
        summary = {
            "original_parsed": original_count,
            "business_duplicates_found": len(business_duplicates),
            "final_stored": len(unique_transactions),
            "total_skipped": len(content_duplicates) + len(business_duplicates)
        }
        
        self.record_deduplication_summary(batch_id, file_fingerprint, summary)
        
        return {
            "status": "completed",
            "batch_id": batch_id,
            "file_fingerprint": file_fingerprint,
            "original_count": original_count,
            "final_count": len(unique_transactions),
            "content_duplicates": len(content_duplicates),
            "business_duplicates": len(business_duplicates),
            "unique_transactions": unique_transactions,
            "deduplication_summary": summary
        }


def get_deduplication_stats(db_conn, days: int = 7) -> Dict:
    """
    Get deduplication statistics for the last N days
    
    Args:
        db_conn: Database connection
        days: Number of days to look back
    
    Returns:
        Dictionary with deduplication statistics
    """
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as batches_processed,
                SUM(original_parsed) as total_parsed,
                SUM(final_stored) as total_stored,
                SUM(total_skipped) as total_skipped,
                ROUND(100.0 * SUM(total_skipped) / SUM(original_parsed), 2) as dedup_percentage
            FROM control.deduplication_summary
            WHERE created_at >= NOW() - INTERVAL '%s days'
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """, (days,))
        
        results = cur.fetchall()
        
        return {
            'daily_stats': [
                {
                    'date': row[0].isoformat() if row[0] else None,
                    'batches_processed': row[1],
                    'total_parsed': row[2],
                    'total_stored': row[3],
                    'total_skipped': row[4],
                    'dedup_percentage': float(row[5]) if row[5] else 0.0
                }
                for row in results
            ]
        }


def get_file_processing_history(db_conn, limit: int = 10) -> List[Dict]:
    """
    Get recent file processing history
    
    Args:
        db_conn: Database connection
        limit: Maximum number of records to return
    
    Returns:
        List of file processing records
    """
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT 
                file_fingerprint,
                processed_at,
                row_count,
                status,
                batch_id
            FROM control.file_processing_log
            ORDER BY processed_at DESC
            LIMIT %s
        """, (limit,))
        
        results = cur.fetchall()
        
        return [
            {
                'file_fingerprint': row[0],
                'processed_at': row[1].isoformat() if row[1] else None,
                'row_count': row[2],
                'status': row[3],
                'batch_id': row[4]
            }
            for row in results
        ]
