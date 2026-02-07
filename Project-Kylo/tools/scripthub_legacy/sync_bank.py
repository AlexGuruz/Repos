from __future__ import annotations

import argparse
import sys
from typing import List
from src.gsheets import load_cfg, svc_from_sa, a1, norm, ensure_id, col_to_a1
from src.rules import load_rules


def _resolve_tab(svc, bank_id: str, tab: str) -> str:
    try:
        meta = svc.spreadsheets().get(spreadsheetId=bank_id).execute()
        available = {s["properties"]["title"] for s in meta.get("sheets", [])}
    except Exception as e:
        raise RuntimeError(f"Failed to read sheet metadata for {bank_id}: {e}")

    if tab in available:
        return tab
    raise RuntimeError(f"Required tab '{tab}' not found in {bank_id}.")


def _run_for_bank_id(cfg: dict, svc, rules: dict, bank_id: str, dry_run: bool, limit: int | None) -> int:
    tab = _resolve_tab(svc, bank_id, cfg["bank_tab"])
    b_col = cfg["bank_company_col"]
    c_col = cfg["bank_source_col"]
    key_col = cfg.get("bank_txn_key_col")
    prov_col = cfg.get("bank_provenance_col")
    max_rows = limit or cfg["rows_read_limit"]

    # Ranges
    src_rng = a1(tab, 2, c_col, max_rows, c_col)
    b_rng = a1(tab, 2, b_col, max_rows, b_col)
    key_rng = a1(tab, 2, key_col, max_rows, key_col) if key_col else None
    prov_rng = a1(tab, 2, prov_col, max_rows, prov_col) if prov_col else None

    # Fetch
    src = svc.spreadsheets().values().get(spreadsheetId=bank_id, range=src_rng).execute().get("values", [])
    cur_b = svc.spreadsheets().values().get(spreadsheetId=bank_id, range=b_rng).execute().get("values", [])
    cur_key = (
        svc.spreadsheets().values().get(spreadsheetId=bank_id, range=key_rng).execute().get("values", []) if key_rng else []
    )
    cur_prov = (
        svc.spreadsheets().values().get(spreadsheetId=bank_id, range=prov_rng).execute().get("values", []) if prov_rng else []
    )

    n = max(len(src), len(cur_b), len(cur_key), len(cur_prov))
    def pad(col):
        col += [[]] * (n - len(col))
        return col

    src = pad(src)
    cur_b = pad(cur_b)
    cur_key = pad(cur_key)
    cur_prov = pad(cur_prov)

    def parse_prov(text: str):
        clean_val, key_val = "", ""
        parts = [p.strip() for p in text.split("|") if p]
        for p in parts:
            if p.startswith("rule:"):
                clean_val = p[5:]
            elif p.startswith("key:"):
                key_val = p[4:]
        return clean_val, key_val

    updates_b, updates_prov, changes, prov_changes, clears = [], [], 0, 0, 0

    for i in range(n):
        s = src[i][0] if src[i] else ""
        b_val = cur_b[i][0] if cur_b[i] else ""
        k_val = cur_key[i][0] if cur_key[i] else ""
        p_val = cur_prov[i][0] if cur_prov[i] else ""

        normalized = norm(s)
        target_company = rules.get(normalized)

        # If provenance exists but key changed (row shifted), clear B and provenance
        if p_val:
            p_clean, p_key = parse_prov(p_val)
            if p_key and k_val and p_key != k_val:
                b_val = ""
                p_val = ""
            # If rule was removed (no active mapping) for this clean key, clear B and provenance
            elif p_clean and (target_company is None or str(target_company).strip() == "") and p_clean == normalized:
                if b_val:
                    clears += 1
                b_val = ""
                p_val = ""

        # If we have a rule, enforce it (overwrite mismatches, fill blanks, or keep if matching)
        if normalized and target_company:
            target_company = str(target_company)
            if b_val != target_company:
                b_val = target_company
                p_val = f"rule:{normalized}|key:{k_val}"
                changes += 1
            else:
                # Backfill provenance even when B already populated, if we have a rule and no provenance yet
                if not p_val:
                    p_val = f"rule:{normalized}|key:{k_val}"
                    prov_changes += 1

        updates_b.append([b_val])
        updates_prov.append([p_val])

    total_changes = changes + prov_changes + clears
    msg = (
        f"Would update {changes} rows; stamp {prov_changes} provenance; clear {clears}."
        if dry_run
        else f"Updating {changes} rows; stamping {prov_changes} provenance; clearing {clears}."
    )
    print(msg)
    if not dry_run and total_changes:
        if prov_rng:
            svc.spreadsheets().values().batchUpdate(
                spreadsheetId=bank_id,
                body={
                    "valueInputOption": "RAW",
                    "data": [
                        {"range": b_rng, "values": updates_b},
                        {"range": prov_rng, "values": updates_prov},
                    ],
                },
            ).execute()
        else:
            svc.spreadsheets().values().update(
                spreadsheetId=bank_id, range=b_rng, valueInputOption="RAW", body={"values": updates_b}
            ).execute()
    return changes


def _run_for_clean_transactions(
    cfg: dict, svc, rules: dict, dry_run: bool, limit: int | None
) -> int:
    """Read Kylo_Config rules (already loaded), write Company IDs to CLEAN TRANSACTIONS tab."""
    clean_id = ensure_id(cfg.get("clean_sheet_id") or cfg["kylo_id"])
    tab = cfg.get("clean_tab") or "CLEAN TRANSACTIONS"
    src_col = int(cfg.get("clean_source_col", 3))
    company_col = int(cfg.get("clean_company_col", 2))
    max_rows = limit or int(cfg.get("rows_read_limit", 10000))

    _resolve_tab(svc, clean_id, tab)
    src_rng = a1(tab, 2, src_col, max_rows, src_col)
    company_rng = a1(tab, 2, company_col, max_rows, company_col)

    src = svc.spreadsheets().values().get(spreadsheetId=clean_id, range=src_rng).execute().get("values", [])
    cur_b = svc.spreadsheets().values().get(spreadsheetId=clean_id, range=company_rng).execute().get("values", [])

    n = max(len(src), len(cur_b))
    def pad(col):
        col += [[]] * (n - len(col))
        return col
    src = pad(src)
    cur_b = pad(cur_b)

    updates_b = []
    changes = 0
    for i in range(n):
        s = src[i][0] if src[i] else ""
        b_val = cur_b[i][0] if cur_b[i] else ""
        normalized = norm(s)
        target_company = rules.get(normalized) if normalized else None
        if normalized and target_company:
            target_company = str(target_company)
            if b_val != target_company:
                updates_b.append((i + 2, target_company))
                changes += 1
            else:
                updates_b.append((i + 2, b_val))
        else:
            updates_b.append((i + 2, (cur_b[i][0] if cur_b[i] else "")))

    b_col_a1 = col_to_a1(company_col)
    values = [[u[1]] for u in updates_b]
    update_rng = f"'{tab}'!{b_col_a1}2:{b_col_a1}{1 + len(values)}"
    msg = f"Would write {changes} Company IDs to CLEAN TRANSACTIONS." if dry_run else f"Writing {changes} Company IDs to CLEAN TRANSACTIONS."
    print(msg)
    if not dry_run and changes and values:
        svc.spreadsheets().values().update(
            spreadsheetId=clean_id,
            range=update_rng,
            valueInputOption="RAW",
            body={"values": values},
        ).execute()
    return changes


def run(cfg_path: str, dry_run: bool = False, limit: int | None = None, years: List[str] | None = None):
    cfg = load_cfg(cfg_path)
    svc = svc_from_sa(cfg["service_account"])

    rules = load_rules(svc, cfg)
    if not rules:
        print("No active rules found; reconciling provenance only.")

    if years:
        print("WARNING: --years is ignored. This sync writes only to bank_id in config.json.")

    bank_id = ensure_id(cfg["bank_id"])
    print(f"Target workbook (BANK): {bank_id}")
    bank_changes = _run_for_bank_id(cfg, svc, rules, bank_id, dry_run, limit)

    clean_id = ensure_id(cfg.get("clean_sheet_id") or cfg["kylo_id"])
    print(f"Target workbook (CLEAN TRANSACTIONS): {clean_id}")
    clean_changes = _run_for_clean_transactions(cfg, svc, rules, dry_run, limit)

    return bank_changes + clean_changes


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config/config.json")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--years", default=None, help="Comma-separated years to align with year_workbooks")
    args = ap.parse_args()
    sys.exit(0 if run(args.config, args.dry_run, args.limit, years=None) is not None else 1)



