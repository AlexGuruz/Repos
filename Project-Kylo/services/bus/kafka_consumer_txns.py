import asyncio, json, os, signal, sys
from aiokafka import AIOKafkaConsumer
from pydantic import ValidationError
import psycopg2
from psycopg2.extras import RealDictCursor

from services.bus.schema import TxnsBatchMessage
from services.mover.service import MoverService
from services.mover.models import BatchMoveRequest, CompanyScope
from services.triage.worker import triage_company_batch
from services.sheets import poster
from services.common.config_loader import load_config

BROKERS = os.getenv("KAFKA_BROKERS","localhost:9092").split(',')
TOPIC = os.getenv("KAFKA_TOPIC_TXNS","txns.company.batches")
GROUP = os.getenv("KAFKA_GROUP_TXNS","kylo-workers-txns")
CLIENT_ID = os.getenv("KAFKA_CLIENT_ID","kylo-consumer")
# Posting toggle: prefer YAML posting.sheets.apply; allow KYLO_SHEETS_POST override
_cfg = None
try:
    _cfg = load_config()
except Exception:
    _cfg = None
DO_POST = os.getenv("KYLO_SHEETS_POST") == "1" if os.getenv("KYLO_SHEETS_POST") is not None else bool((_cfg and _cfg.get("posting.sheets.apply", False)) or False)

def _fetch_pending_items_for_batch(conn, batch_id: str):
    sql = """
      SELECT txn_uid, occurred_at::date AS date, description_norm AS source, amount_cents
        FROM app.pending_txns
       WHERE first_seen_batch = %s AND status = 'open'
       ORDER BY occurred_at, txn_uid
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, (batch_id,))
        return cur.fetchall()

def _build_pending_rows(items, company_id: str):
    # Expected poster headers: date, source, company, amount, target_sheet, target_header, approved
    rows = []
    for it in items:
        amount = float(it["amount_cents"]) / 100.0
        rows.append({
          "values": [
            {"userEnteredValue":{"stringValue": str(it["date"])}},
            {"userEnteredValue":{"stringValue": it["source"]}},
            {"userEnteredValue":{"stringValue": company_id}},
            {"userEnteredValue":{"numberValue": amount}},
            {"userEnteredValue":{"stringValue": ""}},
            {"userEnteredValue":{"stringValue": ""}},
            {"userEnteredValue":{"boolValue": False}},
          ]
        })
    return rows

def _compute_signature(company_id:str, tab_name:str, txn_uids):
    # Use repo's helper for consistent signatures
    from services.sheets.poster import compute_pending_batch_signature
    return compute_pending_batch_signature(company_id, tab_name, list(txn_uids), "v1")

async def process_message(msg: TxnsBatchMessage):
    # 1) Move slice for this company (ingest -> app)
    # Resolve DSN from message; fallback to YAML/global env
    dsn_rw = msg.routing.db_dsn_rw or ((_cfg and _cfg.get("database.global_dsn")) or os.environ.get("KYLO_GLOBAL_DSN"))
    mover = MoverService(global_dsn=dsn_rw,
                         company_dsn_resolver=lambda cid: dsn_rw)
    mover.move_batch(BatchMoveRequest(
        ingest_batch_id=msg.ingest_batch_id,
        companies=[CompanyScope(company_id=msg.company_id)]
    ))

    # 2) Triage unmatched -> pending table
    triage_company_batch(dsn_rw, msg.company_id, msg.batch_id)

    # 3) Build pending batchUpdate; idempotent post
    service = poster._get_service()
    # Ensure tabs/headers/theme exist (idempotent; no-ops if already present)
    ensure_ops = poster.ensure_company_tabs(msg.routing.spreadsheet_id, [msg.company_id])
    if ensure_ops.get("requests"):
        service.spreadsheets().batchUpdate(
            spreadsheetId=msg.routing.spreadsheet_id,
            body=ensure_ops
        ).execute()

    # Resolve sheetId for the "{CID} Pending" tab
    titles_to_ids, _ = poster._fetch_meta(service, msg.routing.spreadsheet_id)
    pending_title = poster.build_tab_name(msg.company_id, "Pending")
    sheet_id = titles_to_ids.get(pending_title)
    if sheet_id is None:
        raise RuntimeError(f"Pending tab not found after ensure: {pending_title}")

    # Pull current batch pending items
    with psycopg2.connect(dsn_rw) as conn:
        items = _fetch_pending_items_for_batch(conn, msg.batch_id)

    if not items:
        return

    rows = _build_pending_rows(items, msg.company_id)
    batch = poster.build_pending_batch_update(sheet_id, rows)

    # Signature is based on txn_uids present in this batch
    sig = _compute_signature(msg.company_id, pending_title, [i["txn_uid"] for i in items])

    with psycopg2.connect(dsn_rw) as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 from control.sheet_posts where company_id=%s and batch_signature=%s limit 1",
                        (msg.company_id, sig))
            seen = cur.fetchone() is not None

        if not seen and DO_POST:
            service.spreadsheets().batchUpdate(
                spreadsheetId=msg.routing.spreadsheet_id,
                body=batch
            ).execute()

        with conn.cursor() as cur:
            cur.execute("""
              insert into control.sheet_posts(company_id, tab_name, batch_signature, row_count)
              values (%s,%s,%s,%s) on conflict do nothing
            """, (msg.company_id, pending_title, sig, len(items)))
        conn.commit()

async def main():
    loop = asyncio.get_running_loop()
    stop = asyncio.Event()
    try:
        for s in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(s, stop.set)
    except NotImplementedError:
        # Windows doesn't support add_signal_handler
        pass

    # Retry connection with exponential backoff
    max_retries = 10
    retry_delay = 2
    consumer = None
    for attempt in range(max_retries):
        try:
            consumer = AIOKafkaConsumer(
                TOPIC, bootstrap_servers=BROKERS, group_id=GROUP, client_id=CLIENT_ID,
                enable_auto_commit=False, auto_offset_reset="earliest",
                metadata_max_age_ms=300000,
                request_timeout_ms=30000,
                connections_max_idle_ms=540000,
                api_version="auto"
            )
            await consumer.start()
            print(f"[INFO] Successfully connected to Kafka brokers: {BROKERS}", file=sys.stderr)
            break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"[WARN] Connection attempt {attempt + 1} failed: {e}, retrying in {retry_delay}s...", file=sys.stderr)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 30)  # Exponential backoff, max 30s
            else:
                print(f"[ERROR] Failed to connect after {max_retries} attempts: {e}", file=sys.stderr)
                raise
    
    if consumer is None:
        raise RuntimeError("Failed to create consumer")
    try:
        while not stop.is_set():
            results = await consumer.getmany(timeout_ms=1000, max_records=50)
            for _, batch in results.items():
                for rec in batch:
                    try:
                        data = json.loads(rec.value.decode("utf-8"))
                        msg = TxnsBatchMessage(**data)
                        await process_message(msg)
                        await consumer.commit()
                    except ValidationError as ve:
                        sys.stderr.write(f"[SKIP BAD MESSAGE] {ve}\n")
                        await consumer.commit()
                    except Exception as e:
                        sys.stderr.write(f"[RETRY txns] {e}\n")
                        await asyncio.sleep(1.0)
                        break
    finally:
        await consumer.stop()

if __name__ == "__main__":
    asyncio.run(main())
