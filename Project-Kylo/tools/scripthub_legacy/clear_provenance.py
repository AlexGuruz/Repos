from __future__ import annotations

from src.gsheets import load_cfg, svc_from_sa, a1, ensure_id


def main():
    cfg = load_cfg("config/config.json")
    svc = svc_from_sa(cfg["service_account"])

    bank_id = ensure_id(cfg["bank_id"]) 
    tab = cfg["bank_tab"]
    prov_col = cfg.get("bank_provenance_col")
    max_rows = cfg["rows_read_limit"]

    if not prov_col:
        print("No provenance column configured.")
        return 0

    prov_rng = a1(tab, 2, prov_col, max_rows, prov_col)
    # Build empty values to clear
    blanks = [[""] for _ in range(max_rows - 1)]
    svc.spreadsheets().values().update(
        spreadsheetId=bank_id, range=prov_rng, valueInputOption="RAW", body={"values": blanks}
    ).execute()
    print("Cleared provenance column.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
