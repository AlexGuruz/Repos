import asyncio, json, os, signal, sys
from aiokafka import AIOKafkaConsumer
from pydantic import ValidationError
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone

from services.bus.schema import PromoteRequestMessage
from services.rules_promoter.service import promote as rules_promote
from services.replay.worker import replay_after_promotion
from services.sheets import poster
from services.common.config_loader import load_config

BROKERS = os.getenv("KAFKA_BROKERS","localhost:9092").split(',')
TOPIC = os.getenv("KAFKA_TOPIC_PROMOTE","rules.promote.requests")
GROUP = os.getenv("KAFKA_GROUP_PROMOTE","kylo-workers-promote")
CLIENT_ID = os.getenv("KAFKA_CLIENT_ID","kylo-consumer")
# Debug: print broker configuration
print(f"[DEBUG] KAFKA_BROKERS env var: {os.getenv('KAFKA_BROKERS', 'NOT SET')}", file=sys.stderr)
print(f"[DEBUG] Using brokers: {BROKERS}", file=sys.stderr)
# Posting toggle: prefer YAML posting.sheets.apply; allow KYLO_SHEETS_POST override
_cfg = None
try:
    _cfg = load_config()
except Exception:
    _cfg = None
DO_POST = os.getenv("KYLO_SHEETS_POST") == "1" if os.getenv("KYLO_SHEETS_POST") is not None else bool((_cfg and _cfg.get("posting.sheets.apply", False)) or False)

def _fetch_active_rules(conn):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
          SELECT rule_json
            FROM app.rules_active
           ORDER BY applied_at, rule_id
        """)
        return [r["rule_json"] for r in cur.fetchall()]

def _build_active_rows(company_id: str, rules):
    # Active headers: Ruleset_Version, Effective_At, Company_ID, Source, Target_Sheet, Target_Header, Match_Notes, Created_At
    today = datetime.now(timezone.utc).date().isoformat()
    rows = []
    for r in rules:
        rows.append({
          "values": [
            {"userEnteredValue":{"stringValue":"v1"}},
            {"userEnteredValue":{"stringValue": today}},
            {"userEnteredValue":{"stringValue": company_id}},
            {"userEnteredValue":{"stringValue": r.get("source","")}},
            {"userEnteredValue":{"stringValue": r.get("target_sheet","")}},
            {"userEnteredValue":{"stringValue": r.get("target_header","")}},
            {"userEnteredValue":{"stringValue": r.get("notes","")}},
            {"userEnteredValue":{"stringValue": today}},
          ]
        })
    return rows

def _compute_active_signature(company_id: str, tab_name: str, rules):
    # Deterministic over stable fields
    import hashlib, json
    material = [json.dumps({"s": r.get("source",""), "t": r.get("target_sheet",""),
                            "h": r.get("target_header","")}, separators=(",",":"))
                for r in rules]
    key = company_id + "|" + tab_name + "|" + "|".join(sorted(material))
    return hashlib.md5(key.encode("utf-8")).hexdigest()

async def process_message(msg: PromoteRequestMessage):
    # 1) Promote company rules (pending->active)
    #    Using promoter service against this company only
    dsn_rw = msg.routing.db_dsn_rw or ((_cfg and _cfg.get("database.global_dsn")) or os.environ.get("KYLO_GLOBAL_DSN"))
    rules_promote(None, {msg.company_id: dsn_rw}, companies=[msg.company_id])

    # 2) Replay pending txns now satisfied by new rules
    replay_after_promotion(dsn_rw, msg.company_id)

    # 3) Build Active batchUpdate; idempotent post
    # Use the rules management workbook, not the company transaction workbook
    rules_management_spreadsheet_id = "1mdLWjezU5uj7R3Rp8bTo5AGPuA4yY81bQux4aAV3kec"
    service = poster._get_service()
    ensure_ops = poster.ensure_company_tabs(rules_management_spreadsheet_id, [msg.company_id])
    if ensure_ops.get("requests"):
        service.spreadsheets().batchUpdate(spreadsheetId=rules_management_spreadsheet_id, body=ensure_ops).execute()

    titles_to_ids, _ = poster._fetch_meta(service, rules_management_spreadsheet_id)
    active_title = poster.build_tab_name(msg.company_id, "Active")
    sheet_id = titles_to_ids.get(active_title)
    if sheet_id is None:
        raise RuntimeError(f"Active tab not found after ensure: {active_title}")

    # Pull active rules and construct rows
    with psycopg2.connect(dsn_rw) as conn:
        rules = _fetch_active_rules(conn)

    rows = _build_active_rows(msg.company_id, rules)
    # Clear rows 2..end and append (batchUpdate only)
    # Determine current rowCount to delete extra rows
    meta = service.spreadsheets().get(spreadsheetId=rules_management_spreadsheet_id).execute()
    row_count = 1000
    for sh in meta.get("sheets", []):
        if int(sh["properties"]["sheetId"]) == sheet_id:
            row_count = int(sh["properties"]["gridProperties"].get("rowCount", 1000))
            break

    ops = []
    # delete rows index [1, row_count) (0-based; keep header at row 0)
    ops.append({
      "deleteDimension": {
        "range": {"sheetId": sheet_id, "dimension": "ROWS", "startIndex": 1, "endIndex": row_count}
      }
    })
    if rows:
        ops.append({"appendCells": {"sheetId": sheet_id, "rows": rows, "fields": "userEnteredValue"}})

    sig = _compute_active_signature(msg.company_id, active_title, rules)

    with psycopg2.connect(dsn_rw) as conn:
        with conn.cursor() as cur:
            cur.execute("select 1 from control.sheet_posts where company_id=%s and batch_signature=%s limit 1",
                        (msg.company_id, sig))
            seen = cur.fetchone() is not None

        if not seen and DO_POST:
            service.spreadsheets().batchUpdate(
                spreadsheetId=rules_management_spreadsheet_id,
                body={"requests": ops}
            ).execute()

        with conn.cursor() as cur:
            cur.execute("""
              insert into control.sheet_posts(company_id, tab_name, batch_signature, row_count)
              values (%s,%s,%s,%s) on conflict do nothing
            """, (msg.company_id, active_title, sig, len(rows)))
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
            results = await consumer.getmany(timeout_ms=1000, max_records=20)
            for _, batch in results.items():
                for rec in batch:
                    try:
                        data = json.loads(rec.value.decode("utf-8"))
                        msg = PromoteRequestMessage(**data)
                        await process_message(msg)
                        await consumer.commit()
                    except ValidationError as ve:
                        sys.stderr.write(f"[SKIP BAD MESSAGE] {ve}\n")
                        await consumer.commit()
                    except Exception as e:
                        sys.stderr.write(f"[RETRY promote] {e}\n")
                        await asyncio.sleep(1.0)
                        break
    finally:
        await consumer.stop()

if __name__ == "__main__":
    asyncio.run(main())
