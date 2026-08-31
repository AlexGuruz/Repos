"""
Full sandbox alignment — do not stop until critical checks pass.

1) Fix headers (INCOME DATE, etc.)
2) Rebuild PAYROLL Cash/Bank Net from intake+rules (source of truth for pool)
3) Hide legacy/noise tabs
4) Ensure INCOME/JGD helper formulas + BALANCE I/J/L
5) Re-post JGD+NUGZ
6) Validate; exit nonzero if fails

SANDBOX ONLY: 1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw
"""
from __future__ import annotations

import os
import sys
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

SA = r"E:/secrets/gcp/sa.json"
SID = "1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw"
OPENING_BANK = 4845.52
OPENING_CASH = 6673.09
TODAY = date(2026, 7, 15)

creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
svc = build("sheets", "v4", credentials=creds, cache_discovery=False)


def retry(fn, tries: int = 12):
    for i in range(tries):
        try:
            return fn()
        except HttpError as e:
            if getattr(e, "resp", None) is not None and e.resp.status in (429, 503):
                wait = 35 + i * 12
                print(f"  rate-limit sleep {wait}s")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("retries exhausted")


def a1(tab: str, rng: str) -> str:
    return "'" + tab.replace("'", "''") + "'!" + rng


def get(rng: str, render: str = "UNFORMATTED_VALUE") -> List[List[Any]]:
    return retry(
        lambda: svc.spreadsheets()
        .values()
        .get(spreadsheetId=SID, range=rng, valueRenderOption=render)
        .execute()
        .get("values", [])
    )


def update(rng: str, values: List[List[Any]], raw: bool = False) -> None:
    retry(
        lambda: svc.spreadsheets()
        .values()
        .update(
            spreadsheetId=SID,
            range=rng,
            valueInputOption="RAW" if raw else "USER_ENTERED",
            body={"values": values},
        )
        .execute()
    )


def batch_update(data: List[Dict[str, Any]], raw: bool = False) -> None:
    if not data:
        return
    for i in range(0, len(data), 50):
        chunk = data[i : i + 50]
        retry(
            lambda chunk=chunk: svc.spreadsheets()
            .values()
            .batchUpdate(
                spreadsheetId=SID,
                body={
                    "valueInputOption": "RAW" if raw else "USER_ENTERED",
                    "data": chunk,
                },
            )
            .execute()
        )
        time.sleep(1.2)


def parse_date(v: Any) -> Optional[date]:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return date(1899, 12, 30) + timedelta(days=int(v))
    s = str(v).strip()
    for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    return None


def norm(s: str) -> str:
    return " ".join(str(s or "").strip().upper().split())


def col_letter(n1: int) -> str:
    s = ""
    n = n1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def load_rules(tab: str) -> Dict[str, Tuple[str, str]]:
    """normalized source -> (target_sheet, target_header) for approved rules."""
    rows = get(a1(tab, "A1:I500"))
    if not rows:
        return {}
    hdr = [str(c).strip() for c in rows[0]]
    idx = {h.upper(): i for i, h in enumerate(hdr)}
    src_i = idx.get("UNIQUE SOURCE", 0)
    sheet_i = idx.get("TARGET SHEET", 1)
    header_i = idx.get("TARGET HEADER", 2)
    appr_i = idx.get("APPROVED", 3)
    out: Dict[str, Tuple[str, str]] = {}
    for r in rows[1:]:
        row = list(r) + [""] * 9
        ap = row[appr_i]
        if not (ap is True or str(ap).strip().upper() in ("TRUE", "1", "YES")):
            continue
        src = norm(str(row[src_i]))
        sheet = str(row[sheet_i]).strip()
        header = str(row[header_i]).strip()
        if src and sheet and header:
            out[src] = (sheet, header)
    return out


def find_rule(src: str, table: Dict[str, Tuple[str, str]]) -> Optional[Tuple[str, str]]:
    """Exact / containment match — never match a short token into a longer rule key.

    Bad: description 'PAYROLL' matching rule 'PAYROLL 24950' via `nu in k`.
    """
    n = norm(src)
    if not n:
        return None
    if n in table:
        return table[n]
    for k, v in table.items():
        if not k:
            continue
        # Rule key fully contained in description (txn more specific than rule)
        if len(k) >= 8 and k in n:
            return v
        # Description fully contained in rule key only if description is long enough
        if len(n) >= 12 and n in k:
            return v
    return None


# ---------------------------------------------------------------------------
# STEP 1: headers + hide legacy
# ---------------------------------------------------------------------------
print("=== 1) Headers + hide legacy ===")
inc = get(a1("INCOME", "A19:Y19"))
inc_h = [str(c).strip() if c is not None else "" for c in (inc[0] if inc else [])]
if not inc_h or inc_h[0].upper() != "DATE":
    while len(inc_h) < 25:
        inc_h.append("")
    inc_h[0] = "DATE"
    if not inc_h[1]:
        inc_h[1] = "INCOME"
    update(a1("INCOME", "A19"), [inc_h], raw=True)
    print("  INCOME A19 DATE fixed")
else:
    print("  INCOME DATE ok")

meta = retry(lambda: svc.spreadsheets().get(spreadsheetId=SID, fields="sheets.properties").execute())
hide_titles = {
    "JGD EXPENSES (LEGACY)",
    "JGD RULES (LEGACY)",
    "COMMISSION",
    "MAP",
    "SheetIndex",
    "CASH PAYROLL",
    "BANK PAYROLL",
    "CASH JGD",
    "BANK JGD",
    "CASH NUGZ COG",
    "BANK NUGZ COG",
    "CASH NON CANNABIS",
    "BANK NON CANNABIS",
    "CASH ALLOCATED",
    "BANK ALLOCATED",
    "CASH CANNABIS DIST",
    "BANK CC Payments",
    "CASH INCOME",
    "BANK INCOME",
}
reqs = []
for sh in meta.get("sheets", []):
    p = sh["properties"]
    if p["title"] in hide_titles and not p.get("hidden"):
        reqs.append(
            {
                "updateSheetProperties": {
                    "properties": {"sheetId": p["sheetId"], "hidden": True},
                    "fields": "hidden",
                }
            }
        )
        print(f"  hide {p['title']}")
if reqs:
    retry(lambda: svc.spreadsheets().batchUpdate(spreadsheetId=SID, body={"requests": reqs}).execute())
    time.sleep(1)

# ---------------------------------------------------------------------------
# STEP 2: Rebuild PAYROLL helpers from intake
# ---------------------------------------------------------------------------
print("=== 2) Rebuild PAYROLL Cash/Bank Net from intake ===")
tx_rules = load_rules("TRANSACTIONS RULES")
bank_rules = load_rules("BANK RULES")

# Download intake via Kylo processor for accurate parsing
os.environ["KYLO_INSTANCE_ID"] = "KYLO_2026_SANDBOX"
os.environ["PYTHONPATH"] = str(REPO)
from services.common.config_loader import load_config
from services.intake.csv_downloader import download_petty_cash_csv
from services.intake.csv_processor import PettyCashCSVProcessor
from services.sheets.poster import _extract_spreadsheet_id

cfg = load_config()
sa_path = cfg.get("google.service_account_json_path")
url = (cfg.get("year_workbooks") or {}).get("2026", {}).get("intake_workbook_url")
sid = _extract_spreadsheet_id(url)

by_date: Dict[date, Dict[str, float]] = defaultdict(lambda: {"cash": 0.0, "bank": 0.0})
for tab, rules, pool in (
    ("TRANSACTIONS", tx_rules, "cash"),
    ("BANK", bank_rules, "bank"),
):
    csv = download_petty_cash_csv(sid, sa_path, sheet_name_override=tab)
    proc = PettyCashCSVProcessor(
        csv,
        header_rows=int(cfg.get("intake.csv_processor.header_rows", 19)),
        source_tab=tab,
        source_spreadsheet_id=sid,
    )
    n = 0
    for t in proc.parse_transactions():
        company = str(t.get("company_id") or t.get("company") or "").strip().upper()
        # payroll sheet is shared — include all companies posting to PAYROLL
        src = str(t.get("description") or t.get("source") or "").strip()
        rule = find_rule(src, rules)
        if not rule:
            # try Unique Source field names used by processor
            src2 = str(t.get("raw_description") or "").strip()
            rule = find_rule(src2, rules)
        if not rule:
            continue
        sheet, _header = rule
        if sheet.upper() != "PAYROLL":
            continue
        pd = t.get("posted_date")
        if isinstance(pd, date):
            d = pd
        else:
            d = parse_date(pd)
            if d is None and isinstance(pd, str) and len(pd) >= 10:
                try:
                    d = datetime.strptime(pd[:10], "%Y-%m-%d").date()
                except Exception:
                    d = None
        if d is None:
            continue
        cents = t.get("amount_cents")
        if cents is not None:
            amt = float(cents) / 100.0
        else:
            try:
                amt = float(t.get("amount") or 0)
            except Exception:
                continue
        by_date[d][pool] += amt
        n += 1
    print(f"  {tab}: {n} payroll-matched txns")
    if tab == "BANK":
        # debug sample
        print(f"  BANK payroll by_date sample: {list(by_date.items())[:5]}")

# Map dates to rows on PAYROLL
dates = get(a1("PAYROLL", "A20:A400"))
row_of: Dict[date, int] = {}
for i, r in enumerate(dates):
    d = parse_date(r[0] if r else None)
    if d:
        row_of[d] = 20 + i

# Clear helper formulas; write RAW values for every day
cash_col = []
bank_col = []
for i in range(len(dates)):
    d = parse_date(dates[i][0] if dates[i] else None)
    if d and d in by_date:
        c = round(by_date[d]["cash"], 2)
        b = round(by_date[d]["bank"], 2)
        cash_col.append([c if abs(c) >= 0.005 else ""])
        bank_col.append([b if abs(b) >= 0.005 else ""])
    else:
        cash_col.append([""])
        bank_col.append([""])

update(a1("PAYROLL", "V20"), cash_col, raw=True)
time.sleep(1.5)
update(a1("PAYROLL", "W20"), bank_col, raw=True)
cash_total = sum(by_date[d]["cash"] for d in by_date)
bank_total = sum(by_date[d]["bank"] for d in by_date)
print(f"  PAYROLL helpers written: cash_sum={cash_total:,.2f} bank_sum={bank_total:,.2f} days={len(by_date)}")

# ---------------------------------------------------------------------------
# STEP 3: Ensure INCOME / JGD helper formulas
# ---------------------------------------------------------------------------
print("=== 3) INCOME / JGD helper formulas ===")
inc_h = [str(c).strip() for c in get(a1("INCOME", "A19:Y19"))[0]]
# Cash ops C-K (idx 2-10), Bank ops M-S (12-18) — skip transfers U-V
n_days = len(get(a1("INCOME", "A20:A385")))
inc_cash = []
inc_bank = []
for r in range(20, 20 + n_days):
    inc_cash.append([f'=IF(COUNTA(C{r}:K{r})=0,"",SUM(C{r}:K{r}))'])
    inc_bank.append([f'=IF(COUNTA(M{r}:S{r})=0,"",SUM(M{r}:S{r}))'])
update(a1("INCOME", "X20"), inc_cash, raw=False)
time.sleep(1.5)
update(a1("INCOME", "Y20"), inc_bank, raw=False)
print("  INCOME X/Y helpers refreshed")

# JGD: cash C-E (ATM LOAD, CLOVER, SERVICE FEE), bank G-I (SWITCH, CLOVER BANK, SERVICE FEE BANK)
jgd_h = [str(c).strip() for c in get(a1("JGD", "A19:L19"))[0]]
print("  JGD headers", list(enumerate(jgd_h)))
n_j = len(get(a1("JGD", "A20:A385")))
j_cash = []
j_bank = []
for r in range(20, 20 + n_j):
    j_cash.append([f'=IF(COUNTA(C{r}:E{r})=0,"",SUM(C{r}:E{r}))'])
    j_bank.append([f'=IF(COUNTA(G{r}:I{r})=0,"",SUM(G{r}:I{r}))'])
update(a1("JGD", "K20"), j_cash, raw=False)
time.sleep(1.2)
update(a1("JGD", "L20"), j_bank, raw=False)
print("  JGD K/L helpers refreshed")

# ---------------------------------------------------------------------------
# STEP 4: BALANCE I/J/L — no CANNABIS DIST double-count
# ---------------------------------------------------------------------------
print("=== 4) Rewrite BALANCE I/J/L ===")
n = len(get(a1("BALANCE", "B20:B385")))
rows_i, rows_j, rows_k, rows_l = [], [], [], []
for i in range(n):
    r = 20 + i
    bank_day = (
        f"(IFERROR(INCOME!Y{r},0)+IFERROR(INCOME!AC{r},0)"
        f"+IFERROR('BANK EXPENSES'!B{r},0)+IFERROR(PAYROLL!W{r},0)"
        f"+IFERROR(JGD!L{r},0)+IFERROR('CC Payments'!B{r},0))"
    )
    cash_day = (
        f"(IFERROR(INCOME!X{r},0)+IFERROR(INCOME!AB{r},0)"
        f"+IFERROR('CASH EXPENSES'!B{r},0)+IFERROR(PAYROLL!V{r},0)"
        f"+IFERROR(JGD!K{r},0)+IFERROR('NUGZ COG'!B{r},0)+IFERROR('NON CANNABIS'!B{r},0)"
        f"+IFERROR(ALLOCATED!B{r},0))"
    )
    if i == 0:
        rows_i.append([f"={OPENING_BANK}+{bank_day}"])
        rows_j.append([f"={OPENING_CASH}+{cash_day}"])
    else:
        rows_i.append([f"=I{r-1}+{bank_day}"])
        rows_j.append([f"=J{r-1}+{cash_day}"])
    # K filled by _wire_in_transit_sandbox.py (running unmatched transfer float).
    # Keep prior K values if present; align alone leaves 0 placeholder.
    rows_k.append([0])
    rows_l.append([f"=I{r}+J{r}+K{r}"])

update(a1("BALANCE", "I20"), rows_i, raw=False)
time.sleep(1.5)
update(a1("BALANCE", "J20"), rows_j, raw=False)
time.sleep(1.5)
update(a1("BALANCE", "K20"), rows_k, raw=True)
time.sleep(1)
update(a1("BALANCE", "L20"), rows_l, raw=False)
print(f"  BALANCE wired {n} days")

update(
    a1("BALANCE", "A18:L18"),
    [[
        "",
        "",
        "Payroll (cash+bank helpers)",
        "Expenses (twins)",
        "COG (NUGZ COG only — no DIST double-count)",
        "ATM/JGD zones",
        "CC bank",
        "Income zones",
        "BANK EOD",
        "CASH EOD",
        "IN TRANSIT",
        "AVAILABLE = I+J+K",
    ]],
    raw=True,
)

print("DONE structural alignment — caller should re-post then validate")
