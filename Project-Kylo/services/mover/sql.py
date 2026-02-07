SLICE_SQL = """
SELECT company_id, txn_uid, posted_date, amount_cents, currency_code,
       description, counterparty_name, memo, category,
       source_stream_id, source_file_fingerprint, row_index_0based, hash_norm
FROM core.transactions_unified
WHERE ingest_batch_id = %(batch_id)s AND company_id = %(company_id)s;
"""

UPSERT_AND_ENQUEUE_SQL = """
WITH src AS (
  SELECT * FROM unnest(
    %(txn_uid)s::uuid[],
    %(company_id)s::text[],
    %(posted_date)s::date[],
    %(amount_cents)s::int[],
    %(currency_code)s::text[],
    %(description)s::text[],
    %(counterparty_name)s::text[],
    %(memo)s::text[],
    %(category)s::text[],
    %(source_stream_id)s::text[],
    %(source_file_fingerprint)s::char(64)[],
    %(row_index_0based)s::int[],
    %(hash_norm)s::char(64)[]
  ) AS t(
    txn_uid, company_id, posted_date, amount_cents, currency_code,
    description, counterparty_name, memo, category,
    source_stream_id, source_file_fingerprint, row_index_0based, hash_norm
  )
),
upsert AS (
  INSERT INTO app.transactions (
    txn_uid, company_id, posted_date, amount_cents, currency_code,
    description, counterparty_name, memo, category,
    source_stream_id, source_file_fingerprint, row_index_0based, hash_norm
  )
  SELECT * FROM src
  ON CONFLICT (txn_uid) DO UPDATE SET
    company_id = EXCLUDED.company_id,
    posted_date = EXCLUDED.posted_date,
    amount_cents = EXCLUDED.amount_cents,
    currency_code = EXCLUDED.currency_code,
    description = EXCLUDED.description,
    counterparty_name = EXCLUDED.counterparty_name,
    memo = EXCLUDED.memo,
    category = EXCLUDED.category,
    source_stream_id = EXCLUDED.source_stream_id,
    source_file_fingerprint = EXCLUDED.source_file_fingerprint,
    row_index_0based = EXCLUDED.row_index_0based,
    hash_norm = EXCLUDED.hash_norm
  WHERE app.transactions.hash_norm IS DISTINCT FROM EXCLUDED.hash_norm
  RETURNING txn_uid
),
enq AS (
  INSERT INTO app.sort_queue (txn_uid, reason)
  SELECT DISTINCT u.txn_uid, 'feed.updated' FROM upsert u
  ON CONFLICT (txn_uid, reason) DO NOTHING
  RETURNING 1
)
SELECT
  (SELECT COUNT(*) FROM upsert) AS affected_txns,
  (SELECT COUNT(*) FROM enq)    AS enqueued;
"""

TEMP_STAGE_CREATE = """
CREATE TEMP TABLE IF NOT EXISTS stg_txn (
  txn_uid uuid,
  company_id text,
  posted_date date,
  amount_cents bigint,
  currency_code text,
  description text,
  counterparty_name text,
  memo text,
  category text,
  source_stream_id text,
  source_file_fingerprint char(64),
  row_index_0based int,
  hash_norm char(64)
) ON COMMIT DROP;
"""

UPSERT_FROM_STAGE = """
WITH upsert AS (
  INSERT INTO app.transactions (
    txn_uid, company_id, posted_date, amount_cents, currency_code,
    description, counterparty_name, memo, category,
    source_stream_id, source_file_fingerprint, row_index_0based, hash_norm
  )
  SELECT
    txn_uid, company_id, posted_date, amount_cents, currency_code,
    description, counterparty_name, memo, category,
    source_stream_id, source_file_fingerprint, row_index_0based, hash_norm
  FROM stg_txn
  ON CONFLICT (txn_uid) DO UPDATE SET
    company_id = EXCLUDED.company_id,
    posted_date = EXCLUDED.posted_date,
    amount_cents = EXCLUDED.amount_cents,
    currency_code = EXCLUDED.currency_code,
    description = EXCLUDED.description,
    counterparty_name = EXCLUDED.counterparty_name,
    memo = EXCLUDED.memo,
    category = EXCLUDED.category,
    source_stream_id = EXCLUDED.source_stream_id,
    source_file_fingerprint = EXCLUDED.source_file_fingerprint,
    row_index_0based = EXCLUDED.row_index_0based,
    hash_norm = EXCLUDED.hash_norm
  WHERE app.transactions.hash_norm IS DISTINCT FROM EXCLUDED.hash_norm
  RETURNING txn_uid
),
enq AS (
  INSERT INTO app.sort_queue (txn_uid, reason)
  SELECT DISTINCT u.txn_uid, 'feed.updated' FROM upsert u
  ON CONFLICT (txn_uid, reason) DO NOTHING
  RETURNING 1
)
SELECT
  (SELECT COUNT(*) FROM upsert) AS affected_txns,
  (SELECT COUNT(*) FROM enq)    AS enqueued;
"""

ADVANCE_WATERMARK_SQL = """
UPDATE control.company_feeds
SET last_batch_id = %(batch_id)s, last_updated_at = now()
WHERE company_id = %(company_id)s AND last_batch_id < %(batch_id)s
RETURNING last_batch_id;
"""

EMIT_OUTBOX_SQL = """
INSERT INTO control.outbox_events(topic, payload, event_key)
VALUES (
  'company.feed.updated',
  jsonb_build_object('company_id', %(company_id)s, 'ingest_batch_id', %(batch_id)s),
  'feed.' || %(company_id)s::text || '.' || %(batch_id)s::text
)
ON CONFLICT DO NOTHING
RETURNING id;
"""


RULES_SNAPSHOT_TRUNCATE = "TRUNCATE app.rules_active;"

RULES_SNAPSHOT_INSERT = """
WITH src AS (
  SELECT * FROM unnest(
    %(rule_id)s::uuid[],
    %(rule_json)s::jsonb[]
  ) AS t(rule_id, rule_json)
)
INSERT INTO app.rules_active (rule_id, rule_json, applied_at)
SELECT rule_id, rule_json, now()
FROM src
ON CONFLICT (rule_id) DO UPDATE
  SET rule_json = EXCLUDED.rule_json,
      applied_at = now();
"""

RULES_ENQUEUE_ALL = """
INSERT INTO app.sort_queue (txn_uid, reason)
SELECT txn_uid, 'rules.updated' FROM app.transactions
ON CONFLICT (txn_uid, reason) DO NOTHING;
"""

EMIT_RULES_OUTBOX = """
INSERT INTO control.outbox_events(topic, payload, event_key)
VALUES (
  'rules.updated',
  jsonb_build_object('company_id', %(company_id)s, 'version', %(version)s),
  'rules.' || %(company_id)s::text || '.' || %(version)s::text
)
ON CONFLICT DO NOTHING
RETURNING id;
"""

MOVER_METRICS_INSERT = """
INSERT INTO control.mover_runs (
  company_id, ingest_batch_id, inserted, updated, enqueued, duration_ms
)
VALUES (
  %(company_id)s, %(batch_id)s, %(inserted)s, %(updated)s, %(enqueued)s, %(duration_ms)s
)
"""

TEMP_STAGE_CREATE = """
CREATE TEMP TABLE stg_txn (
  txn_uid UUID,
  company_id TEXT,
  posted_date DATE,
  amount_cents INTEGER,
  currency_code TEXT,
  description TEXT,
  counterparty_name TEXT,
  memo TEXT,
  category TEXT,
  source_stream_id TEXT,
  source_file_fingerprint CHAR(64),
  row_index_0based INTEGER,
  hash_norm CHAR(64)
) ON COMMIT DROP;
"""

UPSERT_FROM_STAGE = """
WITH upsert AS (
  INSERT INTO app.transactions (
    txn_uid, company_id, posted_date, amount_cents, currency_code,
    description, counterparty_name, memo, category,
    source_stream_id, source_file_fingerprint, row_index_0based, hash_norm
  )
  SELECT
    txn_uid, company_id, posted_date, amount_cents, currency_code,
    description, counterparty_name, memo, category,
    source_stream_id, source_file_fingerprint, row_index_0based, hash_norm
  FROM stg_txn
  ON CONFLICT (txn_uid) DO UPDATE
    SET company_id              = EXCLUDED.company_id,
        posted_date             = EXCLUDED.posted_date,
        amount_cents            = EXCLUDED.amount_cents,
        currency_code           = EXCLUDED.currency_code,
        description             = EXCLUDED.description,
        counterparty_name       = EXCLUDED.counterparty_name,
        memo                    = EXCLUDED.memo,
        category                = EXCLUDED.category,
        source_stream_id        = EXCLUDED.source_stream_id,
        source_file_fingerprint = EXCLUDED.source_file_fingerprint,
        row_index_0based        = EXCLUDED.row_index_0based,
        hash_norm               = EXCLUDED.hash_norm
  WHERE app.transactions.hash_norm IS DISTINCT FROM EXCLUDED.hash_norm
  RETURNING txn_uid
),
enq AS (
  INSERT INTO app.sort_queue (txn_uid, reason)
  SELECT DISTINCT u.txn_uid, 'feed.updated' FROM upsert u
  ON CONFLICT (txn_uid, reason) DO NOTHING
  RETURNING 1
)
SELECT
  (SELECT COUNT(*) FROM upsert) AS affected_txns,
  (SELECT COUNT(*) FROM enq)    AS enqueued;
"""

RULES_SNAPSHOT_TRUNCATE = "TRUNCATE app.rules_active;"

RULES_SNAPSHOT_INSERT = """
WITH src AS (
  SELECT
    (elem->>'rule_id')::uuid    AS rule_id,
    (elem->'rule_json')::jsonb  AS rule_json
  FROM jsonb_array_elements(%(snapshot)s::jsonb) AS elem
)
INSERT INTO app.rules_active (rule_id, rule_json, applied_at)
SELECT rule_id, rule_json, now() FROM src;
"""

RULES_ENQUEUE_ALL = """
INSERT INTO app.sort_queue (txn_uid, reason)
SELECT t.txn_uid, 'rules.updated' FROM app.transactions t
ON CONFLICT (txn_uid, reason) DO NOTHING;
"""

EMIT_RULES_OUTBOX = """
INSERT INTO control.outbox_events (topic, payload, event_key)
VALUES (
  'rules.updated',
  jsonb_build_object('company_id', %(company_id)s, 'version', %(version)s, 'checksum', %(checksum)s),
  'rules.' || %(company_id)s::text || '.' || %(version)s::text
)
ON CONFLICT DO NOTHING
RETURNING id;
"""


RULES_SNAPSHOT_CHECKSUM = """
SELECT 'md5:' || md5(coalesce(string_agg(rule_id::text || '|' || md5(rule_json::text), E'\n' ORDER BY rule_id), '')) AS checksum
FROM app.rules_active;
"""

MOVER_METRICS_INSERT = """
INSERT INTO control.mover_runs
  (run_id, company_id, slice_size, inserted, updated, enqueued, advanced_to_batch, duration_ms, started_at, finished_at)
VALUES
  (%(run_id)s, %(company_id)s, %(slice_size)s, %(inserted)s, %(updated)s, %(enqueued)s, %(advanced_to_batch)s, %(duration_ms)s, %(started_at)s, %(finished_at)s)
ON CONFLICT (run_id, company_id) DO NOTHING;
"""

