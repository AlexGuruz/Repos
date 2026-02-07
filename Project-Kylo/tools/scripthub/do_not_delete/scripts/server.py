from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from src.gsheets import load_cfg, svc_from_sa, a1, norm, ensure_id

CFG_PATH = "config/config.json"
_cfg = load_cfg(CFG_PATH)
_svc = svc_from_sa(_cfg["service_account"])

app = FastAPI()


class Rule(BaseModel):
    clean: str
    company: str


@app.post("/kylo-rule")
def apply_rule(rule: Rule, x_auth: str = Header(None)):
    if x_auth != _cfg["webhook_secret"]:
        raise HTTPException(status_code=401, detail="unauthorized")

    key = norm(rule.clean)
    if not key or not rule.company:
        return {"updated": 0}

    bank_id = ensure_id(_cfg["bank_id"])
    tab = _cfg["bank_tab"]
    b_col = _cfg["bank_company_col"]
    c_col = _cfg["bank_source_col"]
    key_col = _cfg.get("bank_txn_key_col")
    prov_col = _cfg.get("bank_provenance_col")
    max_rows = _cfg["rows_read_limit"]

    src_rng = a1(tab, 2, c_col, max_rows, c_col)
    b_rng = a1(tab, 2, b_col, max_rows, b_col)
    key_rng = a1(tab, 2, key_col, max_rows, key_col) if key_col else None
    prov_rng = a1(tab, 2, prov_col, max_rows, prov_col) if prov_col else None

    src = _svc.spreadsheets().values().get(spreadsheetId=bank_id, range=src_rng).execute().get("values", [])
    cur_b = _svc.spreadsheets().values().get(spreadsheetId=bank_id, range=b_rng).execute().get("values", [])
    cur_key = (
        _svc.spreadsheets().values().get(spreadsheetId=bank_id, range=key_rng).execute().get("values", []) if key_rng else []
    )
    cur_prov = (
        _svc.spreadsheets().values().get(spreadsheetId=bank_id, range=prov_rng).execute().get("values", []) if prov_rng else []
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

    updates_b, updates_prov, changes, clears, reconciles = [], [], 0, 0, 0
    for i in range(n):
        s = src[i][0] if src[i] else ""
        b_val = cur_b[i][0] if cur_b[i] else ""
        k_val = cur_key[i][0] if cur_key[i] else ""
        p_val = cur_prov[i][0] if cur_prov[i] else ""

        if p_val:
            p_clean, p_key = parse_prov(p_val)
            if p_key and k_val and p_key != k_val:
                b_val = ""
                p_val = ""
            elif p_clean and key and p_clean == key and (rule.company is None or str(rule.company).strip() == ""):
                if b_val:
                    clears += 1
                b_val = ""
                p_val = ""
            elif p_clean and key and p_clean == key and b_val and b_val != str(rule.company):
                b_val = str(rule.company)
                p_val = f"rule:{key}|key:{k_val}"
                reconciles += 1

        if not b_val and s and norm(s) == key:
            updates_b.append([rule.company])
            updates_prov.append([f"rule:{key}|key:{k_val}"])
            changes += 1
        else:
            updates_b.append([b_val])
            updates_prov.append([p_val])

    if changes or clears or reconciles:
        if prov_rng:
            _svc.spreadsheets().values().batchUpdate(
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
            _svc.spreadsheets().values().update(
                spreadsheetId=bank_id, range=b_rng, valueInputOption="RAW", body={"values": updates_b}
            ).execute()
    return {"updated": changes, "cleared": clears, "reconciled": reconciles}



