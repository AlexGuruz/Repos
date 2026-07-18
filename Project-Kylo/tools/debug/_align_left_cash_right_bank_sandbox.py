"""
SANDBOX ONLY — physically align target tabs: CASH columns LEFT, BANK columns RIGHT.

Spreadsheet: 1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw
Never touches live 1oNVc-C03ePqLNE76sRUldzpLYsJWb2fo92rkM0_fqNE.

Layout contract (row 19 headers, daily spine row 20+):
  PAYROLL: DATE | Payroll | [cash people] | Payroll Cash Net | | [bank people] | Payroll Bank Net
  JGD:     DATE | ATM | [cash zone] | JGD Cash Net | | [bank zone] | JGD Bank Net
  INCOME:  DATE | INCOME | [cash] | Income Cash Net | | [bank] | Income Bank Net | | transfers | xfer nets
  Twins / singles: keep pool-pure tabs; label day-net col B clearly.

Prints the resulting helper column letters for projection_forecast maps.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

SA = r"E:/secrets/gcp/sa.json"
SID = "1Y9tauvFUxrBnfBk5yrfDFs_nNefEfnvp6jzRyNU2FWw"
assert SID != "1oNVc-C03ePqLNE76sRUldzpLYsJWb2fo92rkM0_fqNE"

creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
svc = build("sheets", "v4", credentials=creds, cache_discovery=False)

OUT_MAP = Path(__file__).resolve().parents[2] / ".kylo" / "instances" / "KYLO_2026_SANDBOX" / "left_right_column_map.json"


def col_letter(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def a1(tab: str, rng: str) -> str:
    return "'" + tab.replace("'", "''") + "'!" + rng


def retry(fn, label: str = "", tries: int = 12):
    for i in range(tries):
        try:
            time.sleep(0.35)
            return fn()
        except HttpError as e:
            status = getattr(getattr(e, "resp", None), "status", None)
            if status in (429, 500, 503) and i < tries - 1:
                wait = 20 + i * 12
                print(f"  rate-limit {label}: sleep {wait}s")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError(f"retry exhausted: {label}")


def get(rng: str, render: str = "UNFORMATTED_VALUE") -> List[List[Any]]:
    return retry(
        lambda: svc.spreadsheets()
        .values()
        .get(spreadsheetId=SID, range=rng, valueRenderOption=render)
        .execute()
        .get("values", []),
        f"get {rng[:48]}",
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
        .execute(),
        f"upd {rng[:48]}",
    )


def clear(rng: str) -> None:
    retry(
        lambda: svc.spreadsheets().values().clear(spreadsheetId=SID, range=rng).execute(),
        f"clr {rng[:48]}",
    )


def pad(row: Sequence[Any], n: int) -> List[Any]:
    out = list(row) + [""] * max(0, n - len(row))
    return out[:n]


def norm(h: Any) -> str:
    return str(h or "").strip().upper()


def hdr_map(headers: Sequence[Any]) -> Dict[str, int]:
    """First-occurrence map (cash-side wins for duplicates)."""
    out: Dict[str, int] = {}
    for i, h in enumerate(headers):
        k = norm(h)
        if k and k not in out:
            out[k] = i
    return out


def hdr_map_last(headers: Sequence[Any]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for i, h in enumerate(headers):
        k = norm(h)
        if k:
            out[k] = i
    return out


def rules_headers(rules_tab: str, sheets: Set[str]) -> Set[str]:
    rows = get(a1(rules_tab, "A1:I500"), "FORMATTED_VALUE")
    if not rows:
        return set()
    hdr = [str(c).strip().upper() for c in rows[0]]
    idx = {h: i for i, h in enumerate(hdr)}
    si, hi = idx.get("TARGET SHEET", 1), idx.get("TARGET HEADER", 2)
    out: Set[str] = set()
    for r in rows[1:]:
        if len(r) <= max(si, hi):
            continue
        if str(r[si]).strip().upper() in sheets:
            h = str(r[hi]).strip()
            if h:
                out.add(h)
    return out


def balance_n() -> int:
    dates = get(a1("BALANCE", "B20:B400"))
    return len(dates)


def remap_rows(
    old_headers: List[str],
    new_headers: List[str],
    old_data: List[List[Any]],
    *,
    date_idx: int = 0,
    skip_headers: Optional[Set[str]] = None,
    duplicate_to_last: Optional[Set[str]] = None,
) -> List[List[Any]]:
    """Copy cells by header name into new layout. Dates stay in col A."""
    skip_headers = {norm(x) for x in (skip_headers or set())}
    duplicate_to_last = {norm(x) for x in (duplicate_to_last or set())}
    first = hdr_map(old_headers)
    new_first = hdr_map(new_headers)
    rows_out: List[List[Any]] = []
    for old in old_data:
        row = [""] * len(new_headers)
        if old:
            row[date_idx] = old[0] if len(old) > 0 else ""
        for h_up, oi in first.items():
            if h_up in skip_headers or h_up == "DATE":
                continue
            if oi >= len(old):
                continue
            v = old[oi]
            if v in ("", None):
                continue
            # Shared names (e.g. GREG WREN): history stays on FIRST/cash zone only.
            ni = new_first.get(h_up)
            if ni is not None:
                row[ni] = v
        rows_out.append(row)
    return rows_out


def align_payroll(n: int) -> Dict[str, str]:
    print("=== PAYROLL left=cash / right=bank ===")
    cash_h = rules_headers("TRANSACTIONS RULES", {"PAYROLL", "CASH PAYROLL"})
    bank_h = rules_headers("BANK RULES", {"PAYROLL", "BANK PAYROLL"})
    old_hdr_row = get(a1("PAYROLL", "A19:BZ19"), "FORMATTED_VALUE")
    old_headers = [str(c).strip() for c in (old_hdr_row[0] if old_hdr_row else [])]
    old_data = get(a1("PAYROLL", f"A20:BZ{19 + n}"), "FORMULA")
    old_helpers = get(a1("PAYROLL", f"V20:W{19 + n}"), "FORMULA")

    # Person columns currently on sheet (preserve visual order), classified by rules.
    people: List[str] = []
    for h in old_headers:
        hu = norm(h)
        if not hu or hu in {"DATE", "PAYROLL", "PAYROLL CASH NET", "PAYROLL BANK NET"}:
            continue
        if h not in people:
            people.append(h)

    cash_people: List[str] = []
    bank_people: List[str] = []
    seen_cash: Set[str] = set()
    for h in people:
        hu = h.upper()
        in_cash = hu in {x.upper() for x in cash_h}
        in_bank = hu in {x.upper() for x in bank_h}
        if in_cash or (not in_bank):
            # orphans (e.g. ROSE) stay cash/left
            if hu not in seen_cash:
                cash_people.append(h)
                seen_cash.add(hu)
        if in_bank:
            bank_people.append(h)
    # Ensure every bank header exists on the right even if missing from sheet
    for h in sorted(bank_h):
        if h.upper() not in {x.upper() for x in bank_people}:
            bank_people.append(h)

    headers = (
        ["DATE", "Payroll"]
        + cash_people
        + ["Payroll Cash Net"]
        + [""]
        + bank_people
        + ["Payroll Bank Net"]
    )
    section = (
        ["", ""]
        + ["CASH ZONE"]
        + [""] * (len(cash_people) - 1)
        + ["EOD"]
        + ["|"]
        + ["BANK ZONE"]
        + [""] * max(0, len(bank_people) - 1)
        + ["EOD"]
    )
    cash_start = 3
    cash_end = 2 + len(cash_people)
    cn_i = cash_end + 1
    bank_start = cn_i + 2
    bank_end = bank_start + len(bank_people) - 1
    bn_i = bank_end + 1

    shared = {x.upper() for x in cash_h} & {x.upper() for x in bank_h}
    data = remap_rows(
        old_headers,
        headers,
        old_data,
        skip_headers={"PAYROLL", "PAYROLL CASH NET", "PAYROLL BANK NET"},
        duplicate_to_last=shared,
    )
    # Ensure length / dates / helpers / B total
    while len(data) < n:
        data.append([""] * len(headers))
    bal_dates = get(a1("BALANCE", "B20:B400"))
    for i in range(n):
        r = 20 + i
        row = pad(data[i], len(headers))
        if i < len(bal_dates) and bal_dates[i]:
            row[0] = bal_dates[i][0]
        cash_rng = f"{col_letter(cash_start)}{r}:{col_letter(cash_end)}{r}"
        bank_rng = f"{col_letter(bank_start)}{r}:{col_letter(bank_end)}{r}"
        # Preserve prior helper values (poster-written pool nets) when present.
        old_c = old_helpers[i][0] if i < len(old_helpers) and old_helpers[i] else ""
        old_b = (
            old_helpers[i][1]
            if i < len(old_helpers) and len(old_helpers[i]) > 1
            else ""
        )
        if old_c not in ("", None):
            row[cn_i - 1] = old_c
        else:
            row[cn_i - 1] = f'=IF(COUNTA({cash_rng})=0,"",SUM({cash_rng}))'
        if old_b not in ("", None):
            row[bn_i - 1] = old_b
        else:
            row[bn_i - 1] = f'=IF(COUNTA({bank_rng})=0,"",SUM({bank_rng}))'
        row[1] = f"=IFERROR({col_letter(cn_i)}{r},0)+IFERROR({col_letter(bn_i)}{r},0)"
        data[i] = row

    clear(a1("PAYROLL", "A18:BZ500"))
    update(a1("PAYROLL", "A18"), [section, headers] + data, raw=False)
    m = {
        "cash_net": col_letter(cn_i),
        "bank_net": col_letter(bn_i),
        "cash_zone": f"{col_letter(cash_start)}:{col_letter(cash_end)}",
        "bank_zone": f"{col_letter(bank_start)}:{col_letter(bank_end)}",
    }
    print(f"  PAYROLL helpers {m['cash_net']}/{m['bank_net']} zones {m['cash_zone']} | {m['bank_zone']}")
    print(f"  cash people={cash_people}")
    print(f"  bank people={bank_people}")
    return m


def align_jgd(n: int) -> Dict[str, str]:
    print("=== JGD helpers at zone ends ===")
    cash_headers = ["ATM LOAD", "CLOVER", "SERVICE FEE"]
    bank_headers = ["SWITCH", "CLOVER (BANK)", "SERVICE FEE (BANK)"]
    old_hdr_row = get(a1("JGD", "A19:BZ19"), "FORMATTED_VALUE")
    old_headers = [str(c).strip() for c in (old_hdr_row[0] if old_hdr_row else [])]
    old_data = get(a1("JGD", f"A20:BZ{19 + n}"), "FORMULA")
    # Also accept un-suffixed bank clover if present historically
    headers = (
        ["DATE", "ATM"]
        + cash_headers
        + ["JGD Cash Net"]
        + [""]
        + bank_headers
        + ["JGD Bank Net"]
    )
    section = (
        ["", ""]
        + ["CASH ZONE"]
        + [""] * (len(cash_headers) - 1)
        + ["EOD"]
        + ["|"]
        + ["BANK ZONE"]
        + [""] * (len(bank_headers) - 1)
        + ["EOD"]
    )
    cash_start, cash_end = 3, 2 + len(cash_headers)
    cn_i = cash_end + 1
    bank_start = cn_i + 2
    bank_end = bank_start + len(bank_headers) - 1
    bn_i = bank_end + 1

    # Map old helper cols if named
    old_first = hdr_map(old_headers)
    data = remap_rows(
        old_headers,
        headers,
        old_data,
        skip_headers={"ATM", "JGD CASH NET", "JGD BANK NET"},
    )
    bal_dates = get(a1("BALANCE", "B20:B400"))
    while len(data) < n:
        data.append([""] * len(headers))
    # Preserve ATM + old helpers where possible
    for i in range(n):
        r = 20 + i
        row = pad(data[i], len(headers))
        if i < len(bal_dates) and bal_dates[i]:
            row[0] = bal_dates[i][0]
        old = pad(old_data[i] if i < len(old_data) else [], len(old_headers))
        if "ATM" in old_first and old_first["ATM"] < len(old):
            row[1] = old[old_first["ATM"]]
        cash_rng = f"{col_letter(cash_start)}{r}:{col_letter(cash_end)}{r}"
        bank_rng = f"{col_letter(bank_start)}{r}:{col_letter(bank_end)}{r}"
        # Always rewrite zone helpers for the NEW column ranges.
        row[cn_i - 1] = f'=IF(COUNTA({cash_rng})=0,"",SUM({cash_rng}))'
        row[bn_i - 1] = f'=IF(COUNTA({bank_rng})=0,"",SUM({bank_rng}))'
        data[i] = row

    clear(a1("JGD", "A18:BZ500"))
    update(a1("JGD", "A18"), [section, headers] + data, raw=False)
    m = {
        "cash_net": col_letter(cn_i),
        "bank_net": col_letter(bn_i),
        "cash_zone": f"{col_letter(cash_start)}:{col_letter(cash_end)}",
        "bank_zone": f"{col_letter(bank_start)}:{col_letter(bank_end)}",
    }
    print(f"  JGD helpers {m['cash_net']}/{m['bank_net']}")
    return m


def align_income(n: int) -> Dict[str, str]:
    print("=== INCOME helpers at zone ends; transfers far right ===")
    TRANSFER_HEADERS = ["FROM BANK", "TO BANK"]

    old_hdr_row = get(a1("INCOME", "A19:BZ19"), "FORMATTED_VALUE")
    old_headers = [str(c).strip() for c in (old_hdr_row[0] if old_hdr_row else [])]
    old_data = get(a1("INCOME", f"A20:BZ{19 + n}"), "FORMULA")
    old_first = hdr_map(old_headers)

    cash_h = [
        "REG 1",
        "REG 2",
        "REG 3",
        "(N) CASH",
        "(N) WHOLESALE",
        "(N) VENMO",
        "MISC SALES",
        "(P) SALES",
        "EMPIRE SALES",
    ]
    if "CASH" in old_first:
        cash_h.append("CASH")
    bank_h = [
        "SQUARE",
        "VENMO",
        "SQUARE FEE",
        "INVESTMENT",
        "INTEREST",
        "CC STATUS",
        "(N) VENMO (BANK)",
    ]
    if "CITIZENS IN/OUT" in old_first:
        bank_h.append("CITIZENS IN/OUT")

    headers = (
        ["DATE", "INCOME"]
        + cash_h
        + ["Income Cash Net"]
        + [""]
        + bank_h
        + ["Income Bank Net"]
        + [""]
        + TRANSFER_HEADERS
        + ["Transfer Cash Net", "Transfer Bank Net"]
    )
    section = (
        ["", ""]
        + ["CASH ZONE"]
        + [""] * (len(cash_h) - 1)
        + ["EOD"]
        + ["|"]
        + ["BANK ZONE"]
        + [""] * (len(bank_h) - 1)
        + ["EOD"]
        + ["|"]
        + ["TRANSFERS"]
        + [""]
        + ["XFER NETS", ""]
    )
    cash_start, cash_end = 3, 2 + len(cash_h)
    cn_i = cash_end + 1
    bank_start = cn_i + 2
    bank_end = bank_start + len(bank_h) - 1
    bn_i = bank_end + 1
    xfer_start = bn_i + 2
    tc_i = xfer_start + len(TRANSFER_HEADERS)
    tb_i = tc_i + 1

    data = remap_rows(
        old_headers,
        headers,
        old_data,
        skip_headers={
            "INCOME",
            "INCOME CASH NET",
            "INCOME BANK NET",
            "TRANSFER CASH NET",
            "TRANSFER BANK NET",
        },
    )
    bal_dates = get(a1("BALANCE", "B20:B400"))
    while len(data) < n:
        data.append([""] * len(headers))
    for i in range(n):
        r = 20 + i
        row = pad(data[i], len(headers))
        if i < len(bal_dates) and bal_dates[i]:
            row[0] = bal_dates[i][0]
        old = pad(old_data[i] if i < len(old_data) else [], len(old_headers))
        cash_rng = f"{col_letter(cash_start)}{r}:{col_letter(cash_end)}{r}"
        bank_rng = f"{col_letter(bank_start)}{r}:{col_letter(bank_end)}{r}"
        # Always rewrite zone helpers for the NEW column ranges (never keep old
        # SUM formulas — they point at pre-layout columns and double-count).
        row[cn_i - 1] = f'=IF(COUNTA({cash_rng})=0,"",SUM({cash_rng}))'
        row[bn_i - 1] = f'=IF(COUNTA({bank_rng})=0,"",SUM({bank_rng}))'
        for label, dest in (
            ("TRANSFER CASH NET", tc_i - 1),
            ("TRANSFER BANK NET", tb_i - 1),
        ):
            if label in old_first and old_first[label] < len(old) and old[old_first[label]] not in ("", None):
                row[dest] = old[old_first[label]]
        row[1] = f"=IFERROR({col_letter(cn_i)}{r},0)+IFERROR({col_letter(bn_i)}{r},0)"
        data[i] = row

    clear(a1("INCOME", "A18:BZ500"))
    # Unmerge leftover A18:A19 banner merges so DATE header can occupy A19.
    try:
        meta = retry(
            lambda: svc.spreadsheets()
            .get(spreadsheetId=SID, fields="sheets(properties(title,sheetId),merges)")
            .execute(),
            "meta income",
        )
        reqs = []
        for s in meta.get("sheets", []):
            if s["properties"]["title"] != "INCOME":
                continue
            sid = s["properties"]["sheetId"]
            for m in s.get("merges", []):
                if m.get("startRowIndex", 0) <= 19 and m.get("endRowIndex", 0) >= 18:
                    reqs.append({"unmergeCells": {"range": {**m, "sheetId": sid}}})
        if reqs:
            retry(
                lambda: svc.spreadsheets()
                .batchUpdate(spreadsheetId=SID, body={"requests": reqs})
                .execute(),
                "unmerge income",
            )
    except Exception as e:
        print(f"  warn unmerge INCOME: {e}")
    update(a1("INCOME", "A18"), [section, headers] + data, raw=False)
    # Ensure DATE header survives (Sheets can drop A19 when A18 section banner is blank).
    update(a1("INCOME", "A19"), [["DATE"]], raw=True)
    m = {
        "cash_net": col_letter(cn_i),
        "bank_net": col_letter(bn_i),
        "xfer_cash_net": col_letter(tc_i),
        "xfer_bank_net": col_letter(tb_i),
        "cash_zone": f"{col_letter(cash_start)}:{col_letter(cash_end)}",
        "bank_zone": f"{col_letter(bank_start)}:{col_letter(bank_end)}",
    }
    print(f"  INCOME helpers cash={m['cash_net']} bank={m['bank_net']} xfer={m['xfer_cash_net']}/{m['xfer_bank_net']}")
    return m


def label_single_pool_tabs() -> None:
    print("=== Label twin/single pool day-net columns ===")
    # CASH EXPENSES / BANK EXPENSES — already twins; clarify banners + B header
    for tab, banner, b_label in (
        ("CASH EXPENSES", "=== CASH EXPENSES (cash pool / left semantics) ===", "Cash Day Net"),
        ("BANK EXPENSES", "=== BANK EXPENSES (bank pool / right semantics) ===", "Bank Day Net"),
        ("NUGZ COG", "=== NUGZ COG (cash pool only — left) ===", "Cash Day Net"),
        ("CC Payments", "=== CC Payments (bank pool — right semantics) ===", "Bank Day Net"),
        ("NON CANNABIS", "=== NON CANNABIS (cash-primary) ===", "Cash Day Net"),
        ("ALLOCATED", "=== ALLOCATED (cash-primary) ===", "Cash Day Net"),
        ("CANNABIS DIST", "=== CANNABIS DIST (cash-primary) ===", "Cash Day Net"),
    ):
        hdr = get(a1(tab, "A19:B19"), "FORMATTED_VALUE")
        row = pad(hdr[0] if hdr else [], 2)
        row[0] = row[0] or "DATE"
        # Keep meaningful B labels; force day-net name when blank / generic
        cur_b = str(row[1]).strip().upper() if len(row) > 1 else ""
        if cur_b in ("", "EXPENSES", "TOTAL", "SUBTOTAL", "CREDIT CARDS", "COG"):
            # NUGZ COG historically had COG in C; B is the day total
            if tab == "NUGZ COG" and cur_b == "COG":
                pass
            row[1] = b_label
        update(a1(tab, "A18"), [[banner]], raw=True)
        update(a1(tab, "A19:B19"), [row[:2]], raw=True)
        print(f"  {tab}: B={row[1]!r}")


def main() -> None:
    print(f"SANDBOX left/right align on {SID}")
    n = balance_n()
    print(f"days={n}")

    payroll = align_payroll(n)
    time.sleep(2)
    jgd = align_jgd(n)
    time.sleep(2)
    income = align_income(n)
    time.sleep(2)
    label_single_pool_tabs()

    column_map = {
        "spreadsheet_id": SID,
        "PAYROLL": payroll,
        "JGD": jgd,
        "INCOME": income,
        "CASH_NET_TARGETS": {
            "CASH EXPENSES": "B",
            "PAYROLL": payroll["cash_net"],
            "JGD": jgd["cash_net"],
            "NUGZ COG": "B",
            "CANNABIS DIST": "B",
            "NON CANNABIS": "B",
            "ALLOCATED": "B",
            "INCOME": income["cash_net"],
        },
        "BANK_NET_TARGETS": {
            "BANK EXPENSES": "B",
            "PAYROLL": payroll["bank_net"],
            "JGD": jgd["bank_net"],
            "CC Payments": "B",
            "INCOME": income["bank_net"],
        },
    }
    OUT_MAP.parent.mkdir(parents=True, exist_ok=True)
    OUT_MAP.write_text(json.dumps(column_map, indent=2), encoding="utf-8")
    print(f"\nWrote column map -> {OUT_MAP}")
    print(json.dumps(column_map, indent=2))

    update(
        a1("SANDBOX README", "A80"),
        [
            ["LEFT=CASH / RIGHT=BANK LAYOUT (owner request)"],
            ["PAYROLL", f"cash helper {payroll['cash_net']} / bank helper {payroll['bank_net']}"],
            ["JGD", f"cash helper {jgd['cash_net']} / bank helper {jgd['bank_net']}"],
            ["INCOME", f"cash helper {income['cash_net']} / bank helper {income['bank_net']} (transfers excluded from G/H)"],
            ["Twins", "CASH EXPENSES + BANK EXPENSES; day net in col B"],
            ["Singles", "NUGZ COG/NON CANNABIS/ALLOCATED/CANNABIS DIST cash; CC Payments bank"],
            ["BALANCE G/H", "SUMIF spine row20+ of helper / twin B columns per pool"],
        ],
        raw=True,
    )
    print("DONE layout align.")


if __name__ == "__main__":
    main()
