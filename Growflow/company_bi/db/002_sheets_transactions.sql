-- Financial transaction sheets ingested from Google Sheets (stashbox SA).
-- SQLite default path: company_bi/db/sheets_transactions.db
-- One workbook per book_year (2022–2026).

CREATE TABLE IF NOT EXISTS ingest_batches (
    batch_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    transaction_rows INTEGER DEFAULT 0,
    money_log_rows  INTEGER DEFAULT 0,
    notes           TEXT
);

CREATE TABLE IF NOT EXISTS sheet_sources (
    source_key          TEXT PRIMARY KEY,
    book_year           INTEGER NOT NULL,
    spreadsheet_id      TEXT NOT NULL,
    spreadsheet_title   TEXT,
    tab_name            TEXT NOT NULL,
    layout_type         TEXT NOT NULL,
    header_row          INTEGER,
    data_start_row      INTEGER,
    last_loaded_at      TEXT
);

CREATE INDEX IF NOT EXISTS idx_sheet_sources_book_year ON sheet_sources(book_year);

CREATE TABLE IF NOT EXISTS transactions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key          TEXT NOT NULL,
    book_year           INTEGER NOT NULL,
    spreadsheet_id      TEXT NOT NULL,
    tab_name            TEXT NOT NULL,
    sheet_row           INTEGER NOT NULL,
    posted_date         TEXT,
    year                INTEGER,
    month               INTEGER,
    day                 INTEGER,
    company             TEXT,
    source              TEXT,
    amount              REAL,
    amount_cents        INTEGER,
    txn_type            TEXT,
    processed           TEXT,
    notes               TEXT,
    extra_json          TEXT,
    raw_row_json        TEXT NOT NULL,
    row_hash            TEXT NOT NULL,
    ingest_batch_id     INTEGER NOT NULL,
    loaded_at           TEXT NOT NULL,
    UNIQUE (source_key, sheet_row, row_hash)
);

CREATE INDEX IF NOT EXISTS idx_txn_book_year ON transactions(book_year);
CREATE INDEX IF NOT EXISTS idx_txn_posted_date ON transactions(posted_date);
CREATE INDEX IF NOT EXISTS idx_txn_year_month ON transactions(year, month);
CREATE INDEX IF NOT EXISTS idx_txn_company ON transactions(company);
CREATE INDEX IF NOT EXISTS idx_txn_source ON transactions(source);
CREATE INDEX IF NOT EXISTS idx_txn_amount ON transactions(amount);
CREATE INDEX IF NOT EXISTS idx_txn_type ON transactions(txn_type);
CREATE INDEX IF NOT EXISTS idx_txn_source_key ON transactions(source_key);
CREATE INDEX IF NOT EXISTS idx_txn_spreadsheet ON transactions(spreadsheet_id);

CREATE TABLE IF NOT EXISTS money_log_lines (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key          TEXT NOT NULL,
    book_year           INTEGER NOT NULL,
    spreadsheet_id      TEXT NOT NULL,
    tab_name            TEXT NOT NULL,
    sheet_row           INTEGER NOT NULL,
    log_date            TEXT,
    year                INTEGER,
    month               INTEGER,
    day                 INTEGER,
    source_name         TEXT,
    c100                REAL,
    c50                 REAL,
    c20                 REAL,
    c10                 REAL,
    c5                  REAL,
    c2                  REAL,
    c1_bill             REAL,
    c1_coin             REAL,
    c50c                REAL,
    c25c                REAL,
    c10c                REAL,
    c5c                 REAL,
    c1c                 REAL,
    line_total          REAL,
    over_short          REAL,
    cashapp             REAL,
    venmo               REAL,
    raw_row_json        TEXT NOT NULL,
    row_hash            TEXT NOT NULL,
    ingest_batch_id     INTEGER NOT NULL,
    loaded_at           TEXT NOT NULL,
    UNIQUE (source_key, sheet_row, row_hash)
);

CREATE INDEX IF NOT EXISTS idx_ml_book_year ON money_log_lines(book_year);
CREATE INDEX IF NOT EXISTS idx_ml_log_date ON money_log_lines(log_date);
CREATE INDEX IF NOT EXISTS idx_ml_year_month ON money_log_lines(year, month);
CREATE INDEX IF NOT EXISTS idx_ml_source_name ON money_log_lines(source_name);
CREATE INDEX IF NOT EXISTS idx_ml_source_key ON money_log_lines(source_key);
CREATE INDEX IF NOT EXISTS idx_ml_spreadsheet ON money_log_lines(spreadsheet_id);
