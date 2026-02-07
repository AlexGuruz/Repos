"""
Triage Worker
-------------
Company-first fork:
 - For a given company + batch, examine newly replicated txns in app.transactions.
 - Match against app.rules_active (latest snapshot). Matching policy: exact on description_norm vs rule.source_norm.
 - If matched: enqueue to app.sort_queue with reason 'feed.updated'.
 - If unmatched: upsert into app.pending_txns and emit a 'pending.ready' outbox event.

Assumptions:
 - app.transactions has columns: txn_uid, occurred_at, amount_cents, description_norm, last_seen_batch
 - app.rules_active payload contains entries with keys: source_norm, target_header, target_sheet
 - control.outbox_events(topic, key, payload) exists; else stub emit_outbox()
Adapt column/table names here if your repo differs (keep SQL changes local & minimal).
"""
import logging
import time
import hashlib
from typing import Dict, List, Tuple
import json
import psycopg2
from psycopg2.extras import execute_values

# Configure structured logging
logger = logging.getLogger(__name__)

def _compute_batch_signature(company_id: str, batch_id: str, txn_count: int) -> str:
    """Compute a unique signature for this batch to prevent duplicate processing"""
    content = f"{company_id}:{batch_id}:{txn_count}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]

def _check_batch_already_processed(conn, company_id: str, batch_id: str, txn_count: int) -> bool:
    """Check if this batch has already been processed to prevent duplicates"""
    batch_signature = _compute_batch_signature(company_id, batch_id, txn_count)
    
    with conn.cursor() as cur:
        cur.execute("""
            select count(*) from control.sheet_posts 
            where company_id = %s and batch_signature = %s
        """, (company_id, batch_signature))
        return cur.fetchone()[0] > 0

def _mark_batch_processed(conn, company_id: str, batch_id: str, txn_count: int, operation: str = "triage") -> None:
    """Mark this batch as processed to prevent duplicate processing"""
    batch_signature = _compute_batch_signature(company_id, batch_id, txn_count)
    
    with conn.cursor() as cur:
        cur.execute("""
            insert into control.sheet_posts (company_id, tab_name, batch_signature, row_count)
            values (%s, %s, %s, %s)
            on conflict (company_id, batch_signature) do nothing
        """, (company_id, f"{operation}_batch", batch_signature, txn_count))

def _load_active_rules_map(conn, company_id: str) -> Dict[str, Dict[str,str]]:
    start_time = time.time()
    with conn.cursor() as cur:
        cur.execute("""
            select payload
            from app.rules_active
            where company_id = %s
            order by version desc
            limit 1
        """, (company_id,))
        row = cur.fetchone()
        if not row or not row[0]:
            logger.info("No active rules found for company", extra={
                "company_id": company_id,
                "rules_count": 0,
                "load_time_ms": round((time.time() - start_time) * 1000, 2)
            })
            return {}
        payload = row[0]  # jsonb -> dict/list via psycopg2
        # Build source_norm -> rule dict
        rules = {}
        for item in payload:
            sn = item.get("source_norm") or item.get("source")
            if not sn:
                continue
            rules[sn] = {
                "target_header": item.get("target_header"),
                "target_sheet": item.get("target_sheet"),
            }
        
        logger.info("Loaded active rules for company", extra={
            "company_id": company_id,
            "rules_count": len(rules),
            "load_time_ms": round((time.time() - start_time) * 1000, 2)
        })
        return rules

def _fetch_txns_for_batch(conn, company_id: str, batch_id: str) -> List[Tuple]:
    start_time = time.time()
    with conn.cursor() as cur:
        cur.execute("""
            select txn_uid, description_norm, amount_cents, occurred_at
            from app.transactions
            where last_seen_batch = %s
              and company_id = %s
        """, (batch_id, company_id))
        txns = cur.fetchall()
        
        logger.info("Fetched transactions for batch", extra={
            "batch_id": batch_id,
            "txn_count": len(txns),
            "fetch_time_ms": round((time.time() - start_time) * 1000, 2)
        })
        return txns

def _enqueue_sorted(conn, company_id: str, batch_id: str, txn_uids: List[str]) -> None:
    if not txn_uids:
        return
    
    start_time = time.time()
    with conn.cursor() as cur:
        execute_values(cur, """
            insert into app.sort_queue (reason, txn_uid, company_id, queued_at, batch_id)
            values %s
            on conflict (reason, txn_uid) do nothing
        """, [( 'feed.updated', uid, company_id, 'now()', batch_id) for uid in txn_uids])
    
    logger.info("Enqueued matched transactions", extra={
        "batch_id": batch_id,
        "enqueued_count": len(txn_uids),
        "enqueue_time_ms": round((time.time() - start_time) * 1000, 2)
    })

def _upsert_pending(conn, company_id: str, batch_id: str, rows: List[Tuple[str,str,int,str]]) -> None:
    """
    rows: list of (txn_uid, description_norm, amount_cents, occurred_at)
    """
    if not rows:
        return
    
    start_time = time.time()
    with conn.cursor() as cur:
        execute_values(cur, """
            insert into app.pending_txns
                (txn_uid, company_id, first_seen_batch, last_seen_batch, occurred_at, description_norm, amount_cents, row_checksum)
            values %s
            on conflict (txn_uid) do update
            set last_seen_batch = excluded.last_seen_batch,
                company_id     = excluded.company_id,
                amount_cents   = excluded.amount_cents,
                description_norm = excluded.description_norm,
                row_checksum   = excluded.row_checksum,
                updated_at     = now()
        """, [
            (uid, company_id, batch_id, batch_id, occurred_at, dnorm, amount, f"{uid}:{amount}:{dnorm}")
            for (uid, dnorm, amount, occurred_at) in rows
        ])
    
    logger.info("Upserted pending transactions", extra={
        "batch_id": batch_id,
        "pending_count": len(rows),
        "upsert_time_ms": round((time.time() - start_time) * 1000, 2)
    })

def _emit_outbox(conn, company_id: str, batch_id: str, txn_uids: List[str], topic: str) -> None:
    if not txn_uids:
        return
    
    start_time = time.time()
    with conn.cursor() as cur:
        cur.execute("""
            insert into control.outbox_events (topic, key, payload)
            values (%s, %s, %s::jsonb)
        """, (topic, company_id, json.dumps({"batch_id": batch_id, "txn_uids": txn_uids})))
    
    logger.info("Emitted outbox event", extra={
        "company_id": company_id,
        "batch_id": batch_id,
        "topic": topic,
        "txn_count": len(txn_uids),
        "emit_time_ms": round((time.time() - start_time) * 1000, 2)
    })

def _record_metrics(conn, company_id: str, batch_id: str, operation: str, 
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
        """, (company_id, batch_id, operation, matched, unmatched, resolved,
              total_time_ms, load_time_ms, match_time_ms, update_time_ms))

def triage_company_batch(pg_dsn: str, company_id: str, batch_id: str) -> Dict[str,int]:
    """
    Entry point for job runners.
    Returns counts: {"matched": N, "unmatched": M}
    """
    overall_start_time = time.time()
    
    logger.info("Starting triage for company batch", extra={
        "company_id": company_id,
        "batch_id": batch_id
    })
    
    conn = psycopg2.connect(pg_dsn)
    try:
        # Check for duplicate processing
        txns = _fetch_txns_for_batch(conn, company_id, batch_id)
        already = _check_batch_already_processed(conn, company_id, batch_id, len(txns))
        
        rules_map = _load_active_rules_map(conn, company_id)
        
        # Match transactions against rules
        match_start_time = time.time()
        matched, unmatched = [], []
        for uid, dnorm, amount, occurred_at in txns:
            if dnorm in rules_map:
                matched.append(uid)
            else:
                unmatched.append((uid, dnorm, amount, occurred_at))
        
        match_time_ms = round((time.time() - match_start_time) * 1000, 2)
        logger.info("Completed transaction matching", extra={
            "company_id": company_id,
            "batch_id": batch_id,
            "matched_count": len(matched),
            "unmatched_count": len(unmatched),
            "match_time_ms": match_time_ms
        })
        
        if not already:
            _enqueue_sorted(conn, company_id, batch_id, matched)
            _upsert_pending(conn, company_id, batch_id, unmatched)
        _emit_outbox(conn, company_id, batch_id, [u for u in (uid for uid,_,_,_ in unmatched)], topic="pending.ready")
        
        # Mark batch as processed
        if not already:
            _mark_batch_processed(conn, company_id, batch_id, len(txns))
        
        conn.commit()
        
        overall_time_ms = round((time.time() - overall_start_time) * 1000, 2)
        logger.info("Completed triage for company batch", extra={
            "company_id": company_id,
            "batch_id": batch_id,
            "matched": len(matched),
            "unmatched": len(unmatched),
            "total_time_ms": overall_time_ms
        })
        
        # Record metrics
        _record_metrics(conn, company_id, batch_id, "triage", 
                       len(matched), len(unmatched), 0, overall_time_ms, 
                       match_time_ms=match_time_ms)
        
        # Even when skipping a duplicate batch, return stable counts.
        return {"matched": len(matched), "unmatched": len(unmatched)}
    except Exception as e:
        logger.error("Error during triage", extra={
            "company_id": company_id,
            "batch_id": batch_id,
            "error": str(e),
            "total_time_ms": round((time.time() - overall_start_time) * 1000, 2)
        })
        # Rollback only affects this company's data
        conn.rollback()
        raise
    finally:
        conn.close()
