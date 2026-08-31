"""Organize sandbox INCOME + BALANCE columns for Cash vs Bank readability.

SANDBOX ONLY. Does not touch live 2026 workbook.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build

pointer = json.loads(Path(r"E:/Repos/Project-Kylo/config/sandbox_2026_liquidity.json").read_text())
SID = pointer["sandbox_spreadsheet_id"]
SA = r"E:/secrets/gcp/sa.json"

creds = service_account.Credentials.from_service_account_file(
    SA, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)


def a1(tab: str, rng: str) -> str:
    return "'" + tab.replace("'", "''") + "'!" + rng


def get(rng: str, render: str = "UNFORMATTED_VALUE") -> List[List[Any]]:
    return (
        sheets.spreadsheets()
        .values()
        .get(spreadsheetId=SID, range=rng, valueRenderOption=render)
        .execute()
        .get("values", [])
    )


# ---------------------------------------------------------------------------
# INCOME: rebuild header order into Cash | spacer | Bank | spacer | Transfers
# Kylo matches by header name, so renaming columns is fine if values move with names.
# ---------------------------------------------------------------------------

# Read current header + data block (rows 19-385, cols A-S historically)
raw = get(a1("INCOME", "A19:Z385"))
if not raw:
    raise SystemExit("No INCOME data")

header_row = [str(c).strip() if c is not None else "" for c in (raw[0] if raw else [])]
# pad
while len(header_row) < 26:
    header_row.append("")

# Map header name -> column index in current data (0-based within A19:Z)
name_to_idx: Dict[str, int] = {}
for i, h in enumerate(header_row):
    if h and h.upper() not in ("INCOME", "DATE", ""):
        name_to_idx[h.upper()] = i

print("Current INCOME headers:", header_row[:20])


def col_vals(name: str) -> List[Any]:
    """Return values for rows 20-385 (data rows) for a named header."""
    key = name.upper()
    if key not in name_to_idx:
        return [""] * max(0, len(raw) - 1)
    idx = name_to_idx[key]
    out = []
    for row in raw[1:]:  # from former row 20
        out.append(row[idx] if idx < len(row) else "")
    return out


# Desired layout (row 19 headers). A=date stays col0 of sheet; B=total formula
# New order after A,B:
CASH_HEADERS = [
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
BANK_HEADERS = [
    "SQUARE",
    "VENMO",
    "SQUARE FEE",
    "INVESTMENT",
    "INTEREST",
    "CC STATUS",
]
TRANSFER_HEADERS = [
    "FROM BANK",
    "TO BANK",
]

# Collect series
date_col = []
for row in raw[1:]:
    date_col.append(row[0] if row else "")

series: Dict[str, List[Any]] = {}
for h in CASH_HEADERS + BANK_HEADERS + TRANSFER_HEADERS:
    series[h] = col_vals(h)

n = len(date_col)
# Build new matrix rows 19.. 
# Columns: A date, B total, C.. cash, spacer, bank..., spacer, transfers
new_header = (
    ["", "INCOME"]
    + CASH_HEADERS
    + [""]  # spacer after cash
    + BANK_HEADERS
    + [""]  # spacer after bank
    + TRANSFER_HEADERS
)
section_row = (
    ["", ""]
    + ["CASH POOL"]
    + [""] * (len(CASH_HEADERS) - 1)
    + ["|"]
    + ["BANK FEED"]
    + [""] * (len(BANK_HEADERS) - 1)
    + ["|"]
    + ["TRANSFERS (memo; excluded from Available)"]
    + [""] * (len(TRANSFER_HEADERS) - 1)
)

# Compute column letters for B sum: cash+bank only (skip spacers + transfers)
# A=1 B=2, cash starts at C=3
cash_start = 3  # C
cash_end = 2 + len(CASH_HEADERS)  # inclusive
spacer1 = cash_end + 1
bank_start = spacer1 + 1
bank_end = bank_start + len(BANK_HEADERS) - 1
spacer2 = bank_end + 1
xfer_start = spacer2 + 1
xfer_end = xfer_start + len(TRANSFER_HEADERS) - 1


def col_letter(n1: int) -> str:
    s = ""
    n = n1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


cash_rng = f"{col_letter(cash_start)}{{r}}:{col_letter(cash_end)}{{r}}"
bank_rng = f"{col_letter(bank_start)}{{r}}:{col_letter(bank_end)}{{r}}"

data_rows = []
for i in range(n):
    r = 20 + i  # sheet row
    row = [date_col[i], f"=SUM({cash_rng.format(r=r)})+SUM({bank_rng.format(r=r)})"]
    for h in CASH_HEADERS:
        row.append(series[h][i] if i < len(series[h]) else "")
    row.append("")  # spacer
    for h in BANK_HEADERS:
        row.append(series[h][i] if i < len(series[h]) else "")
    row.append("")  # spacer
    for h in TRANSFER_HEADERS:
        row.append(series[h][i] if i < len(series[h]) else "")
    data_rows.append(row)

# Clear wide area then write row 18 section, 19 headers, 20+ data
sheets.spreadsheets().values().clear(
    spreadsheetId=SID, range=a1("INCOME", "A18:Z400")
).execute()

body = [section_row, new_header] + data_rows
sheets.spreadsheets().values().update(
    spreadsheetId=SID,
    range=a1("INCOME", "A18"),
    valueInputOption="USER_ENTERED",
    body={"values": body},
).execute()
print(f"Wrote INCOME layout: {len(data_rows)} daily rows")
print("Header:", new_header)
print(f"B formula uses cash {col_letter(cash_start)}:{col_letter(cash_end)} + bank {col_letter(bank_start)}:{col_letter(bank_end)}")
print(f"Transfers sit at {col_letter(xfer_start)}:{col_letter(xfer_end)} (excluded from B)")

# ---------------------------------------------------------------------------
# BALANCE: clarify section labels on row 18
# ---------------------------------------------------------------------------
bal_section = [[
    "",
    "",
    "<<< category nets (Payroll/Expenses/COG/ATM/CC/Income)",
    "",
    "",
    "",
    "",
    "",
    "BANK EOD",
    "CASH EOD",
    "IN TRANSIT",
    "AVAILABLE = Bank+Cash+InTransit",
]]
sheets.spreadsheets().values().update(
    spreadsheetId=SID,
    range=a1("BALANCE", "A18:L18"),
    valueInputOption="RAW",
    body={"values": bal_section},
).execute()

# Ensure I19:L19 headers stay clear
sheets.spreadsheets().values().update(
    spreadsheetId=SID,
    range=a1("BALANCE", "I19:L19"),
    valueInputOption="RAW",
    body={"values": [["Bank EOD", "Cash EOD", "In Transit", "AVAILABLE"]]},
).execute()

# README note
sheets.spreadsheets().values().update(
    spreadsheetId=SID,
    range=a1("SANDBOX README", "A48"),
    valueInputOption="RAW",
    body={
        "values": [
            ["INCOME column layout (organized)"],
            ["Row 18", "Section banners: CASH POOL | BANK FEED | TRANSFERS"],
            ["Row 19", "Headers in those groups; blank spacer columns between"],
            ["Col B", "Sums CASH + BANK only — transfers excluded (Available stays honest)"],
            ["BALANCE I-L", "Bank EOD / Cash EOD / In Transit / AVAILABLE"],
        ]
    },
).execute()

print("DONE column organization")
print(pointer["sandbox_url"])
