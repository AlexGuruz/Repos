"""
Ingest Google Sheets financial data into SQLite for filterable queries.

Supports:
- **transactions** layout: DATE / COMPANY / SOURCE / AMOUNT (+ optional Type, Processed, NOTES)
- **money_log** layout: petty-cash denomination rows (2022/2023 money logs)
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from company_bi.lib.sources import (
    detect_transaction_columns,
    parse_amount,
    parse_date_to_ymd,
)

_COMPANY_BI_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_DB = _COMPANY_BI_ROOT / "db" / "sheets_transactions.db"
_DDL = _COMPANY_BI_ROOT / "db" / "002_sheets_transactions.sql"
_CONFIG = _COMPANY_BI_ROOT / "config" / "sheets_db_sources.yaml"

_MONEY_LOG_COLS = {
    3: "c100",
    4: "c50",
    5: "c20",
    6: "c10",
    7: "c5",
    8: "c2",
    9: "c1_bill",
    11: "c1_coin",
    12: "c50c",
    13: "c25c",
    14: "c10c",
    15: "c5c",
    16: "c1c",
    17: "line_total",
    19: "over_short",
    20: "cashapp",
    21: "venmo",
}


def load_sheets_db_config() -> dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise ImportError("PyYAML required: pip install pyyaml") from exc
    if not _CONFIG.exists():
        return {}
    with open(_CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_db_path(config: dict[str, Any] | None = None) -> Path:
    cfg = config or load_sheets_db_config()
    raw = (cfg.get("default_db_path") or "company_bi/db/sheets_transactions.db").strip()
    p = Path(raw)
    if not p.is_absolute():
        p = _COMPANY_BI_ROOT.parent / raw
    return p


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _row_hash(parts: list[Any]) -> str:
    payload = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cell_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


def _cell_num(val: Any) -> float | None:
    if val is None or val == "":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().replace(",", "").replace("$", "").strip()
    if not s or s in ("-", "$ -"):
        return None
    negative = "(" in s and ")" in s
    s = s.replace("(", "").replace(")", "").strip()
    try:
        n = float(s)
        return -n if negative else n
    except ValueError:
        return None


def _norm_header(cell: Any) -> str:
    return re.sub(r"\s+", " ", str(cell or "").strip().upper())


def _find_transaction_header(rows: list[list[Any]]) -> tuple[int, dict[str, int]]:
    """Return (header_row_0based, col_map)."""
    for i, row in enumerate(rows[:30]):
        headers = [_norm_header(c) for c in row]
        if "DATE" in headers and ("AMOUNT" in headers or "TOTAL" in headers):
            col_map: dict[str, int] = {}
            for j, h in enumerate(headers):
                if h == "DATE":
                    col_map["date"] = j
                elif h == "COMPANY":
                    col_map["company"] = j
                elif h in ("SOURCE", "DESCRIPTION", "DESC"):
                    col_map["source"] = j
                elif h in ("AMOUNT", "TOTAL"):
                    col_map["amount"] = j
                elif h == "TYPE":
                    col_map["type"] = j
                elif h in ("PROCESSED", "APPROVED"):
                    col_map["processed"] = j
                elif h == "NOTES":
                    col_map["notes"] = j
            if "date" in col_map and "amount" in col_map:
                return i, col_map
    date_col, company_col, source_col, amount_col, start = detect_transaction_columns(rows)
    return max(0, start - 1), {
        "date": date_col,
        "company": company_col,
        "source": source_col,
        "amount": amount_col,
    }


def _pad_row(row: list[Any], width: int) -> list[Any]:
    if len(row) >= width:
        return row
    return row + [""] * (width - len(row))


def parse_transaction_rows(
    rows: list[list[Any]],
    *,
    source_key: str,
    spreadsheet_id: str,
    tab_name: str,
    header_row_1based: int | None = None,
    data_start_row_1based: int | None = None,
) -> tuple[list[dict[str, Any]], int, int]:
    """Parse transaction-layout rows. Returns (records, header_row_1based, data_start_1based)."""
    if not rows:
        return [], 1, 2
    if header_row_1based and data_start_row_1based:
        header_idx = header_row_1based - 1
        data_start = data_start_row_1based - 1
        header_row = rows[header_idx] if header_idx < len(rows) else rows[0]
        col_map = {}
        for j, h in enumerate(_norm_header(c) for c in header_row):
            if h == "DATE":
                col_map["date"] = j
            elif h == "COMPANY":
                col_map["company"] = j
            elif h in ("SOURCE", "DESCRIPTION"):
                col_map["source"] = j
            elif h in ("AMOUNT", "TOTAL"):
                col_map["amount"] = j
            elif h == "TYPE":
                col_map["type"] = j
            elif h in ("PROCESSED", "APPROVED"):
                col_map["processed"] = j
            elif h == "NOTES":
                col_map["notes"] = j
    else:
        header_idx, col_map = _find_transaction_header(rows)
        data_start = header_idx + 1
        header_row_1based = header_idx + 1
        data_start_row_1based = data_start + 1

    known = set(col_map.values())
    out: list[dict[str, Any]] = []
    for i in range(data_start, len(rows)):
        row = rows[i]
        if not row or all(_cell_str(c) == "" for c in row):
            continue
        date_col = col_map.get("date", 0)
        if date_col >= len(row):
            continue
        ymd = parse_date_to_ymd(row[date_col])
        amount_col = col_map.get("amount", 3)
        amt = parse_amount(row[amount_col] if len(row) > amount_col else None)
        if amt is None:
            continue
        company = _cell_str(row[col_map["company"]]) if "company" in col_map and len(row) > col_map["company"] else ""
        source = _cell_str(row[col_map["source"]]) if "source" in col_map and len(row) > col_map["source"] else ""
        if ymd is not None and ymd[0] < 1990:
            ymd = None
        if ymd is None and not source:
            continue
        if ymd is None and amt == 0:
            continue
        y, mo, d = ymd if ymd else (None, None, None)
        txn_type = _cell_str(row[col_map["type"]]) if "type" in col_map and len(row) > col_map["type"] else ""
        processed_raw = row[col_map["processed"]] if "processed" in col_map and len(row) > col_map["processed"] else None
        processed = "" if processed_raw is None else str(processed_raw)
        notes = _cell_str(row[col_map["notes"]]) if "notes" in col_map and len(row) > col_map["notes"] else ""
        if not notes and len(row) > 6:
            trailing = _cell_str(row[6])
            if trailing.lower().startswith("posted "):
                notes = trailing

        extra: dict[str, Any] = {}
        for j, cell in enumerate(row):
            if j in known:
                continue
            if _cell_str(cell):
                extra[f"col_{j}"] = cell

        sheet_row = i + 1
        posted_date = f"{y:04d}-{mo:02d}-{d:02d}" if ymd else None
        raw_json = json.dumps(row, ensure_ascii=False, default=str)
        row_hash = _row_hash([spreadsheet_id, tab_name, sheet_row, posted_date, company, source, amt])
        out.append({
            "source_key": source_key,
            "spreadsheet_id": spreadsheet_id,
            "tab_name": tab_name,
            "sheet_row": sheet_row,
            "posted_date": posted_date,
            "year": y,
            "month": mo,
            "day": d,
            "company": company,
            "source": source,
            "amount": amt,
            "amount_cents": int(round(amt * 100)),
            "txn_type": txn_type,
            "processed": processed,
            "notes": notes,
            "extra_json": json.dumps(extra, ensure_ascii=False, default=str) if extra else None,
            "raw_row_json": raw_json,
            "row_hash": row_hash,
        })
    return out, header_row_1based or (header_idx + 1), data_start_row_1based or (data_start + 1)


def parse_money_log_rows(
    rows: list[list[Any]],
    *,
    source_key: str,
    spreadsheet_id: str,
    tab_name: str,
    data_start_row_1based: int = 5,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    data_start = data_start_row_1based - 1
    for i in range(data_start, len(rows)):
        row = _pad_row(rows[i], 22)
        date_raw = row[1] if len(row) > 1 else None
        source_name = _cell_str(row[2]) if len(row) > 2 else ""
        if not source_name and date_raw in (None, ""):
            continue
        ymd = parse_date_to_ymd(date_raw)
        if ymd is not None and ymd[0] < 1990:
            ymd = None
        if ymd is None:
            continue
        y, mo, d = ymd
        fields: dict[str, Any] = {v: _cell_num(row[col]) for col, v in _MONEY_LOG_COLS.items() if col < len(row)}
        for name in _MONEY_LOG_COLS.values():
            fields.setdefault(name, None)
        log_date = f"{y:04d}-{mo:02d}-{d:02d}"
        sheet_row = i + 1
        raw_json = json.dumps(row, ensure_ascii=False, default=str)
        row_hash = _row_hash([spreadsheet_id, tab_name, sheet_row, log_date, source_name, raw_json])
        rec = {
            "source_key": source_key,
            "spreadsheet_id": spreadsheet_id,
            "tab_name": tab_name,
            "sheet_row": sheet_row,
            "log_date": log_date,
            "year": y,
            "month": mo,
            "day": d,
            "source_name": source_name,
            "raw_row_json": raw_json,
            "row_hash": row_hash,
        }
        rec.update(fields)
        out.append(rec)
    return out


def ensure_schema(conn: sqlite3.Connection) -> None:
    ddl = _DDL.read_text(encoding="utf-8")
    tables_part, _, indexes_part = ddl.partition("CREATE INDEX")
    conn.executescript(tables_part)
    for table in ("sheet_sources", "transactions", "money_log_lines"):
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if "book_year" not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN book_year INTEGER")
    if indexes_part:
        conn.executescript("CREATE INDEX" + indexes_part)
    conn.commit()


def _book_year_from_source(source_key: str, src: dict[str, Any]) -> int:
    year = src.get("year")
    if year is not None:
        return int(year)
    if source_key.startswith("year_") and source_key[5:].isdigit():
        return int(source_key[5:])
    raise ValueError(f"Source {source_key!r} is missing required 'year' in config")


def _fetch_tab_values(service: Any, spreadsheet_id: str, tab: str) -> list[list[Any]]:
    resp = service.spreadsheets().values().get(
        spreadsheetId=spreadsheet_id,
        range=f"'{tab}'!A1:ZZ",
        valueRenderOption="UNFORMATTED_VALUE",
    ).execute()
    return resp.get("values") or []


def _spreadsheet_title(service: Any, spreadsheet_id: str) -> str:
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="properties.title").execute()
    return meta.get("properties", {}).get("title") or spreadsheet_id


def ingest_all_sources(
    *,
    db_path: Path | None = None,
    service: Any | None = None,
    config: dict[str, Any] | None = None,
    source_keys: list[str] | None = None,
) -> dict[str, Any]:
    cfg = config or load_sheets_db_config()
    path = db_path or get_db_path(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)

    if service is None:
        from lib.stashbox_sheets_auth import sheets_service

        service = sheets_service()

    sources: dict[str, Any] = cfg.get("sources") or {}
    if source_keys:
        sources = {k: v for k, v in sources.items() if k in source_keys}

    started = _utc_now()
    conn = sqlite3.connect(path)
    try:
        ensure_schema(conn)
        active_keys = list(sources.keys())
        if active_keys:
            placeholders = ",".join("?" * len(active_keys))
            conn.execute(f"DELETE FROM transactions WHERE source_key NOT IN ({placeholders})", active_keys)
            conn.execute(f"DELETE FROM money_log_lines WHERE source_key NOT IN ({placeholders})", active_keys)
            conn.execute(f"DELETE FROM sheet_sources WHERE source_key NOT IN ({placeholders})", active_keys)
        cur = conn.execute(
            "INSERT INTO ingest_batches (started_at, notes) VALUES (?, ?)",
            (started, f"sources={','.join(sources.keys())}"),
        )
        batch_id = cur.lastrowid
        txn_total = 0
        ml_total = 0
        loaded_at = _utc_now()

        for source_key, src in sources.items():
            sid = src["spreadsheet_id"]
            tab = src.get("tab") or "Sheet1"
            layout = src.get("layout") or "transactions"
            book_year = _book_year_from_source(source_key, src)
            title = _spreadsheet_title(service, sid)
            rows = _fetch_tab_values(service, sid, tab)

            conn.execute("DELETE FROM transactions WHERE source_key = ?", (source_key,))
            conn.execute("DELETE FROM money_log_lines WHERE source_key = ?", (source_key,))

            header_row = src.get("header_row")
            data_start = src.get("data_start_row")

            if layout == "money_log":
                records = parse_money_log_rows(
                    rows,
                    source_key=source_key,
                    spreadsheet_id=sid,
                    tab_name=tab,
                    data_start_row_1based=int(data_start or 5),
                )
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO money_log_lines (
                        source_key, book_year, spreadsheet_id, tab_name, sheet_row,
                        log_date, year, month, day, source_name,
                        c100, c50, c20, c10, c5, c2, c1_bill, c1_coin,
                        c50c, c25c, c10c, c5c, c1c, line_total, over_short, cashapp, venmo,
                        raw_row_json, row_hash, ingest_batch_id, loaded_at
                    ) VALUES (
                        :source_key, :book_year, :spreadsheet_id, :tab_name, :sheet_row,
                        :log_date, :year, :month, :day, :source_name,
                        :c100, :c50, :c20, :c10, :c5, :c2, :c1_bill, :c1_coin,
                        :c50c, :c25c, :c10c, :c5c, :c1c, :line_total, :over_short, :cashapp, :venmo,
                        :raw_row_json, :row_hash, :ingest_batch_id, :loaded_at
                    )
                    """,
                    [{**r, "book_year": book_year, "ingest_batch_id": batch_id, "loaded_at": loaded_at} for r in records],
                )
                ml_total += len(records)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sheet_sources (
                        source_key, book_year, spreadsheet_id, spreadsheet_title, tab_name,
                        layout_type, header_row, data_start_row, last_loaded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (source_key, book_year, sid, title, tab, layout, header_row, data_start, loaded_at),
                )
            else:
                records, hdr, data_row = parse_transaction_rows(
                    rows,
                    source_key=source_key,
                    spreadsheet_id=sid,
                    tab_name=tab,
                    header_row_1based=header_row,
                    data_start_row_1based=data_start,
                )
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO transactions (
                        source_key, book_year, spreadsheet_id, tab_name, sheet_row,
                        posted_date, year, month, day, company, source, amount, amount_cents,
                        txn_type, processed, notes, extra_json, raw_row_json, row_hash,
                        ingest_batch_id, loaded_at
                    ) VALUES (
                        :source_key, :book_year, :spreadsheet_id, :tab_name, :sheet_row,
                        :posted_date, :year, :month, :day, :company, :source, :amount, :amount_cents,
                        :txn_type, :processed, :notes, :extra_json, :raw_row_json, :row_hash,
                        :ingest_batch_id, :loaded_at
                    )
                    """,
                    [{**r, "book_year": book_year, "ingest_batch_id": batch_id, "loaded_at": loaded_at} for r in records],
                )
                txn_total += len(records)
                conn.execute(
                    """
                    INSERT OR REPLACE INTO sheet_sources (
                        source_key, book_year, spreadsheet_id, spreadsheet_title, tab_name,
                        layout_type, header_row, data_start_row, last_loaded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (source_key, book_year, sid, title, tab, layout, hdr, data_row, loaded_at),
                )

        finished = _utc_now()
        conn.execute(
            """
            UPDATE ingest_batches
            SET finished_at = ?, transaction_rows = ?, money_log_rows = ?
            WHERE batch_id = ?
            """,
            (finished, txn_total, ml_total, batch_id),
        )
        conn.commit()
        return {
            "db_path": str(path),
            "batch_id": batch_id,
            "transaction_rows": txn_total,
            "money_log_rows": ml_total,
            "sources": list(sources.keys()),
        }
    finally:
        conn.close()
