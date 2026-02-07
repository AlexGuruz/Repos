"""
Replay Worker
-------------
On new rules snapshot, move matching pending items into the matched path:
 - Mark app.pending_txns.status='resolved'
 - Enqueue txn_uid into app.sort_queue (reason='feed.updated')
Idempotent: safe to run multiple times.
"""
import logging
import time
from typing import Dict
import psycopg2
from psycopg2.extras import execute_values

# Configure structured logging
logger = logging.getLogger(__name__)

def _record_metrics(conn, company_id: str, operation: str, 
                   matched: int, unmatched: int, resolved: int, 
                   total_time_ms: int, load_time_ms: int = None, 
                   match_time_ms: int = None, update_time_ms: int = None) -> None:
    """Record metrics for monitoring and performance tracking"""
    with conn.cursor() as cur:
        cur.execute("""
            insert into control.triage_metrics 
            (company_id, batch_id, operation, matched_count, unmatched_count, resolved_count,
             total_time_ms, load_time_ms, match_time_ms, update_time_ms)
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (company_id, "replay", operation, matched, unmatched, resolved,
              total_time_ms, load_time_ms, match_time_ms, update_time_ms))

def replay_after_promotion(pg_dsn: str, company_id: str) -> Dict[str,int]:
    overall_start_time = time.time()
    
    logger.info("Starting replay after promotion", extra={
        "company_id": company_id
    })
    
    conn = psycopg2.connect(pg_dsn)
    try:
        # Load latest rules
        rules_start_time = time.time()
        with conn.cursor() as cur:
            # Build a temp table of latest rules for fast exact join
            cur.execute("""
                with latest as (
                  select payload
                  from app.rules_active
                  where company_id = %s
                  order by version desc
                  limit 1
                )
                select coalesce(jsonb_agg(elem), '[]'::jsonb)
                from latest, jsonb_array_elements(coalesce(latest.payload, '[]'::jsonb)) elem
            """, (company_id,))
            arr = cur.fetchone()[0]  # list of rules
        
        rules_time_ms = round((time.time() - rules_start_time) * 1000, 2)
        logger.info("Loaded latest rules for replay", extra={
            "company_id": company_id,
            "rules_count": len(arr),
            "load_time_ms": rules_time_ms
        })
        
        # Load open pending rows
        pending_start_time = time.time()
        with conn.cursor() as cur:
            cur.execute(
                "select txn_uid, description_norm from app.pending_txns where status='open' and company_id = %s",
                (company_id,),
            )
            pend = cur.fetchall()
        
        pending_time_ms = round((time.time() - pending_start_time) * 1000, 2)
        logger.info("Loaded open pending transactions", extra={
            "company_id": company_id,
            "pending_count": len(pend),
            "load_time_ms": pending_time_ms
        })
        
        # Find matching transactions
        match_start_time = time.time()
        rule_set = { (r.get("source_norm") or r.get("source")) for r in arr }
        to_resolve = [uid for (uid, dnorm) in pend if dnorm in rule_set]
        
        match_time_ms = round((time.time() - match_start_time) * 1000, 2)
        logger.info("Identified matching pending transactions", extra={
            "company_id": company_id,
            "matching_count": len(to_resolve),
            "match_time_ms": match_time_ms
        })
        
        if not to_resolve:
            overall_time_ms = round((time.time() - overall_start_time) * 1000, 2)
            logger.info("No transactions to resolve", extra={
                "company_id": company_id,
                "resolved": 0,
                "total_time_ms": overall_time_ms
            })
            
            # Record metrics even for no-op
            _record_metrics(conn, company_id, "replay", 0, len(pend), 0, overall_time_ms, 
                           rules_time_ms, match_time_ms)
            return {"resolved": 0}
        
        # Mark resolved and enqueue
        update_start_time = time.time()
        with conn.cursor() as cur:
            execute_values(cur, "update app.pending_txns as p set status='resolved', updated_at=now() from (values %s) as v(uid) where p.txn_uid=v.uid", [(u,) for u in to_resolve])
            execute_values(
                cur,
                "insert into app.sort_queue (reason, txn_uid, company_id, queued_at, batch_id) values %s on conflict (reason, txn_uid) do nothing",
                [('feed.updated', u, company_id, 'now()', 'replay') for u in to_resolve],
            )
        
        update_time_ms = round((time.time() - update_start_time) * 1000, 2)
        logger.info("Updated pending status and enqueued transactions", extra={
            "company_id": company_id,
            "resolved_count": len(to_resolve),
            "update_time_ms": update_time_ms
        })
        
        conn.commit()
        
        overall_time_ms = round((time.time() - overall_start_time) * 1000, 2)
        logger.info("Completed replay after promotion", extra={
            "company_id": company_id,
            "resolved": len(to_resolve),
            "total_time_ms": overall_time_ms
        })
        
        # Record metrics
        _record_metrics(conn, company_id, "replay", len(to_resolve), len(pend) - len(to_resolve), 
                       len(to_resolve), overall_time_ms, rules_time_ms, match_time_ms, update_time_ms)
        
        return {"resolved": len(to_resolve)}
    except Exception as e:
        logger.error("Error during replay", extra={
            "company_id": company_id,
            "error": str(e),
            "total_time_ms": round((time.time() - overall_start_time) * 1000, 2)
        })
        # Rollback only affects this company's data
        conn.rollback()
        raise
    finally:
        conn.close()
