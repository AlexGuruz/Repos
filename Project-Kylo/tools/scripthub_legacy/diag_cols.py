from __future__ import annotations

import argparse
import string
from collections import Counter
from src.gsheets import load_cfg, svc_from_sa, ensure_id


def col_letter(idx1: int) -> str:
    s = ""
    c = idx1
    while c:
        c, r = divmod(c - 1, 26)
        s = string.ascii_uppercase[r] + s
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.json")
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    cfg = load_cfg(args.config)
    svc = svc_from_sa(cfg["service_account"])
    kylo_id = ensure_id(cfg["kylo_id"])
    tab = cfg["kylo_tab"]

    # Read header A1:Z1
    hdr = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=kylo_id, range=f"{tab}!A1:Z1")
        .execute()
        .get("values", [[]])[0]
    )
    print("Headers A..Z:")
    for i, name in enumerate(hdr, start=1):
        print(f"  {col_letter(i)}: {name}")

    # Sample first N rows A..Z to detect boolean-heavy column (approval)
    vals = (
        svc.spreadsheets()
        .values()
        .get(spreadsheetId=kylo_id, range=f"{tab}!A2:Z{args.limit}")
        .execute()
        .get("values", [])
    )
    col_counts = []
    max_cols = max((len(r) for r in vals), default=0)
    for c in range(max_cols):
        col = [ (r[c] if len(r) > c else "").strip().upper() for r in vals ]
        ctr = Counter(col)
        trues = ctr.get("TRUE", 0)
        falses = ctr.get("FALSE", 0)
        nonempty = sum(1 for x in col if x)
        col_counts.append((c+1, trues, falses, nonempty))

    likely_bool = sorted(col_counts, key=lambda t: (-(t[1]+t[2]), -t[1]))
    print("\nTop boolean-like columns (1-based index, TRUE, FALSE, nonempty):")
    for c, t, f, ne in likely_bool[:5]:
        print(f"  {col_letter(c)}({c}): TRUE={t}, FALSE={f}, nonempty={ne}")


if __name__ == "__main__":
    main()


