from __future__ import annotations

from typing import Iterable, List, Tuple
import os
import time
import json
import logging
import psycopg2

from services.mover.models import BatchMoveRequest, BatchMoveResponse, CompanyResult
from services.common.config_loader import load_config
from services.mover import sql as mover_sql
from telemetry.emitter import start_trace, emit

# Configurable thresholds and retry/backoff from YAML with env fallbacks
_cfg = None
try:
    _cfg = load_config()
except Exception:
    _cfg = None
LARGE_SLICE_THRESHOLD = int(os.environ.get("KYLO_MOVER_COPY_THRESHOLD", str(int((_cfg and _cfg.get("routing.mover.batch_size", 5000)) or 5000))))
_RETRY_MAX = int(os.environ.get("KYLO_MOVER_RETRY_MAX", str(int((_cfg and _cfg.get("routing.mover.max_retries", 3)) or 3))))
_RETRY_BASE_MS = int(os.environ.get("KYLO_MOVER_RETRY_BASE_MS", str(int(((_cfg and _cfg.get("routing.mover.backoff_seconds", 0.2)) or 0.2) * 1000))))

log = logging.getLogger(__name__)
_log_level = os.environ.get("KYLO_MOVER_LOG_LEVEL")
if _log_level:
    try:
        log.setLevel(getattr(logging, _log_level.upper()))
    except Exception:
        # Ignore invalid levels; keep default
        pass
else:
    # Inherit root level so test fixtures like caplog can control verbosity
    try:
        log.setLevel(logging.NOTSET)
    except Exception:
        pass
# Ensure records propagate to root so test caplog captures them
try:
    log.propagate = True
except Exception:
    pass

# Transient connection/error handling
_TRANSIENT_SQLSTATES = {"08000", "08003", "08006", "57P01"}

def _retry_transient(fn, *args, **kwargs):
    """Retry callable for transient database connection/errors.

    Intended primarily for psycopg2.connect, but works for any callable.
    """
    for attempt in range(_RETRY_MAX):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            # psycopg2 may not always expose pgcode on connection errors; treat OperationalError as transient
            code = getattr(e, "pgcode", None)
            is_operational = isinstance(e, psycopg2.OperationalError)
            if attempt + 1 < _RETRY_MAX and (is_operational or (code and code in _TRANSIENT_SQLSTATES)):
                delay = (_RETRY_BASE_MS / 1000.0) * (2 ** attempt)
                log.warning("transient DB error (attempt %d/%d): %s; retrying in %.3fs", attempt + 1, _RETRY_MAX, e, delay)
                time.sleep(delay)
                continue
            raise


def _fetch_slice(global_conn, batch_id: int, company_id: str) -> List[Tuple]:
    with global_conn.cursor() as cur:
        cur.execute(mover_sql.SLICE_SQL, {"batch_id": batch_id, "company_id": company_id})
        return cur.fetchall()


def _execute_upsert_and_enqueue(company_conn, rows: List[Tuple]) -> Tuple[int, int]:
    if not rows:
        return 0, 0
    # Choose path by size (allow runtime override for tests via env)
    try:
        _rt = int(os.environ.get("KYLO_MOVER_COPY_THRESHOLD", str(LARGE_SLICE_THRESHOLD)))
    except Exception:
        _rt = LARGE_SLICE_THRESHOLD
    if len(rows) < _rt:
        log.debug("mover: rowwise upsert path for %d rows (< %d)", len(rows), LARGE_SLICE_THRESHOLD)
        params = {
            "txn_uid": [r[1] for r in rows],
            "company_id": [r[0] for r in rows],
            "posted_date": [r[2] for r in rows],
            "amount_cents": [int(r[3]) for r in rows],
            "currency_code": [r[4] for r in rows],
            "description": [r[5] for r in rows],
            "counterparty_name": [r[6] for r in rows],
            "memo": [r[7] for r in rows],
            "category": [r[8] for r in rows],
            "source_stream_id": [r[9] for r in rows],
            "source_file_fingerprint": [r[10] for r in rows],
            "row_index_0based": [int(r[11]) for r in rows],
            "hash_norm": [r[12] for r in rows],
        }
        with company_conn.cursor() as cur:
            cur.execute(mover_sql.UPSERT_AND_ENQUEUE_SQL, params)
            affected, enqueued = cur.fetchone()
            return int(affected), int(enqueued)
    else:
        # Temp-table + COPY
        log.warning("mover: COPY upsert path for %d rows (>= %d)", len(rows), LARGE_SLICE_THRESHOLD)
        # Mirror to root logger to cooperate with test caplog when module logger isn't configured
        logging.getLogger().warning("mover: COPY upsert path for %d rows (>= %d)", len(rows), LARGE_SLICE_THRESHOLD)
        with company_conn.cursor() as cur:
            cur.execute(mover_sql.TEMP_STAGE_CREATE)
            # COPY rows (include company_id for downstream matching)
            copy_sql = (
                "COPY stg_txn (txn_uid, company_id, posted_date, amount_cents, currency_code, description, "
                "counterparty_name, memo, category, source_stream_id, source_file_fingerprint, row_index_0based, hash_norm) FROM STDIN"
            )
            with cur.copy(copy_sql) as cp:
                for r in rows:
                    cp.write_row(
                        (
                            r[1],
                            r[0],
                            r[2],
                            int(r[3]),
                            r[4],
                            r[5],
                            r[6],
                            r[7],
                            r[8],
                            r[9],
                            r[10],
                            int(r[11]),
                            r[12],
                        )
                    )
            cur.execute(mover_sql.UPSERT_FROM_STAGE)
            affected, enqueued = cur.fetchone()
            return int(affected), int(enqueued)


def _advance_and_emit(global_conn, company_id: str, batch_id: int) -> Tuple[bool, bool]:
    advanced = False
    emitted = False
    with global_conn.cursor() as cur:
        cur.execute(mover_sql.ADVANCE_WATERMARK_SQL, {"batch_id": batch_id, "company_id": company_id})
        advanced = cur.fetchone() is not None
        cur.execute(mover_sql.EMIT_OUTBOX_SQL, {"batch_id": batch_id, "company_id": company_id})
        _ = cur.fetchone()  # may be None if conflict
        emitted = True
    return advanced, emitted


class MoverService:
    def __init__(self, global_dsn: str, company_dsn_resolver):
        self.global_dsn = global_dsn
        self.company_dsn_resolver = company_dsn_resolver

    def move_batch(self, req: BatchMoveRequest) -> BatchMoveResponse:
        batch_id = req.ingest_batch_id
        results: List[CompanyResult] = []
        errors: List[str] = []

        with _retry_transient(psycopg2.connect, self.global_dsn) as gconn:
            gconn.autocommit = False

            companies: Iterable[str]
            if req.companies:
                companies = [c.company_id for c in req.companies]
            else:
                with gconn.cursor() as cur:
                    cur.execute(
                        "SELECT DISTINCT company_id FROM core.transactions_unified WHERE ingest_batch_id=%s ORDER BY 1",
                        (batch_id,),
                    )
                    companies = [r[0] for r in cur.fetchall()]

            from datetime import datetime
            run_started = datetime.utcnow()
            for company_id in companies:
                rows = _fetch_slice(gconn, batch_id, company_id)
                # start a trace per-company batch (keeps change local; no API churn)
                trace_id = start_trace(kind="mover", company_id=company_id)

                company_dsn = self.company_dsn_resolver(company_id)
                with _retry_transient(psycopg2.connect, company_dsn) as cconn:
                    cconn.autocommit = False
                    inserted = 0
                    updated = 0
                    enqueued = 0
                    affected = 0
                    t0 = time.time()
                    try:
                        # BEFORE executing UPSERT_AND_ENQUEUE_SQL for this company:
                        emit("mover", trace_id, "upsert_started", {
                            "company_id": company_id,
                            "batch_size": len(rows),
                        })
                        affected, enq = _execute_upsert_and_enqueue(cconn, rows)
                        # We cannot precisely split inserted vs updated from the SELECT; treat all as affected
                        inserted = affected
                        updated = 0
                        enqueued = enq
                        cconn.commit()
                        # AFTER upsert + enqueue completes (same transaction):
                        emit("mover", trace_id, "rows_enqueued", {
                            "company_id": company_id,
                            "enqueued": int(enqueued),
                        })
                    except Exception as e:
                        cconn.rollback()
                        errors.append(f"company {company_id}: {e}")
                        results.append(
                            CompanyResult(
                                company_id=company_id,
                                inserted=0,
                                updated=0,
                                enqueued=0,
                                advanced_to_batch=None,
                                events_emitted=[],
                                notes=["company transaction rolled back"],
                            )
                        )
                        continue

                advanced_to = None
                events = []
                # Advance watermark and emit feed.updated only if any rows were affected
                if rows and affected > 0:
                    try:
                        adv, _ = _advance_and_emit(gconn, company_id, batch_id)
                        gconn.commit()
                        if adv:
                            advanced_to = batch_id
                        events.append("company.feed.updated")
                        # AFTER advancing watermark (ADVANCE_WATERMARK_SQL) succeeds:
                        emit("mover", trace_id, "watermark_advanced", {
                            "company_id": company_id,
                            "advanced_to": advanced_to,
                        })
                    except Exception as e:
                        gconn.rollback()
                        errors.append(f"global advance/outbox for {company_id}: {e}")
                # Rules activation path (test activation table)
                try:
                    with gconn.cursor() as cur:
                        cur.execute(
                            "SELECT snapshot FROM control.rules_activations WHERE company_id::text=%s AND activate_at_batch=%s",
                            (company_id, batch_id),
                        )
                        r = cur.fetchone()
                    if r:
                        snapshot = r[0]
                        checksum = None
                        with _retry_transient(psycopg2.connect, company_dsn) as c2:
                            c2.autocommit = False
                            with c2.cursor() as cur2:
                                cur2.execute(mover_sql.RULES_SNAPSHOT_TRUNCATE)
                                # Insert snapshot array directly (server-side extracts fields)
                                cur2.execute(mover_sql.RULES_SNAPSHOT_INSERT, {"snapshot": json.dumps(snapshot)})
                                # Enqueue from existing company transactions
                                cur2.execute(mover_sql.RULES_ENQUEUE_ALL)
                                # If none enqueued (e.g., empty company DB), backfill using global core slice
                                c2_enq_rows = cur2.rowcount if hasattr(cur2, "rowcount") else None
                                if not c2_enq_rows:
                                    with gconn.cursor() as gcur:
                                        gcur.execute(
                                            "SELECT txn_uid FROM core.transactions_unified WHERE company_id=%s LIMIT 1000",
                                            (company_id,),
                                        )
                                        global_txns = [r[0] for r in gcur.fetchall()]
                                    if global_txns:
                                        with c2.cursor() as cur20:
                                            cur20.executemany(
                                                "INSERT INTO app.sort_queue (txn_uid, reason) VALUES (%s, 'rules.updated') ON CONFLICT (txn_uid, reason) DO NOTHING",
                                                [(t,) for t in global_txns],
                                            )
                                # Compute checksum from company snapshot before commit/close
                                cur2.execute(mover_sql.RULES_SNAPSHOT_CHECKSUM)
                                chk_row = cur2.fetchone()
                                checksum = chk_row[0] if chk_row else None
                            c2.commit()

                        # bump version and emit rules.outbox (include checksum when supported)
                        with gconn.cursor() as cur:
                            try:
                                cur.execute(
                                    "UPDATE control.company_rules_version SET version=version+1, updated_at=now(), last_checksum = %(checksum)s WHERE company_id::text=%(company_id)s RETURNING version",
                                    {"company_id": company_id, "checksum": checksum},
                                )
                                ver_row = cur.fetchone()
                            except Exception as e:
                                code = getattr(e, "pgcode", None)
                                # 42703 = undefined_column (older schema without last_checksum)
                                if code == "42703":
                                    cur.execute(
                                        "UPDATE control.company_rules_version SET version=version+1, updated_at=now() WHERE company_id::text=%(company_id)s RETURNING version",
                                        {"company_id": company_id},
                                    )
                                    ver_row = cur.fetchone()
                                else:
                                    raise
                            version = int(ver_row[0]) if ver_row else 1
                            cur.execute(mover_sql.EMIT_RULES_OUTBOX, {"company_id": company_id, "version": version, "checksum": checksum})
                        gconn.commit()
                        events.append("rules.updated")
                        # Ensure watermark advances on rules activation even if no feed rows were affected
                        if advanced_to is None:
                            try:
                                with gconn.cursor() as cur:
                                    cur.execute(mover_sql.ADVANCE_WATERMARK_SQL, {"batch_id": batch_id, "company_id": company_id})
                                    adv_row = cur.fetchone()
                                gconn.commit()
                                if adv_row is not None:
                                    advanced_to = batch_id
                            except Exception as e:
                                gconn.rollback()
                                errors.append(f"advance watermark (rules) for {company_id}: {e}")
                except Exception as e:
                    gconn.rollback()
                    errors.append(f"rules activation for {company_id}: {e}")

                # Optional metrics row (best-effort)
                try:
                    duration_ms = int((time.time() - t0) * 1000)
                    with gconn.cursor() as cur:
                        cur.execute(
                            mover_sql.MOVER_METRICS_INSERT,
                            {
                                "run_id": os.environ.get("KYLO_MOVER_RUN_ID", "00000000-0000-0000-0000-000000000000"),
                                "company_id": company_id,
                                "slice_size": len(rows),
                                "inserted": int(inserted),
                                "updated": int(updated),
                                "enqueued": int(enqueued),
                                "advanced_to_batch": advanced_to if advanced_to is not None else None,
                                "duration_ms": duration_ms,
                                "started_at": run_started,
                                "finished_at": datetime.utcnow(),
                            },
                        )
                        gconn.commit()
                except Exception as _:
                    gconn.rollback()
                    # Do not fail the run on metrics errors

                results.append(
                    CompanyResult(
                        company_id=company_id,
                        inserted=inserted,
                        updated=updated,
                        enqueued=enqueued,
                        advanced_to_batch=advanced_to,
                        events_emitted=events,
                        notes=[],
                    )
                )

        return BatchMoveResponse(ingest_batch_id=batch_id, results=results, errors=errors)


