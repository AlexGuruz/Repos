## Isolated Remodel Scaffold

This folder contains an isolated dev scaffold for the remodel effort that can be moved as a unit.

### Contents
- `requirements.txt` — minimal Python deps for local testing
- `pipeline/template/` — reusable per-company pipeline scaffold
- `run_stub.py` — minimal runner wiring dummy components (no real I/O)
- `tests/` — basic test harness (pytest)

### Setup
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### Run the stub
```powershell
python run_stub.py
```

### Test
```powershell
pytest -q
```

### Notes
- Environment variables go in a local `.env` next to this README (see keys in the main project). Do not commit secrets.
- This scaffold is for structure and developer ergonomics; integrate with the main app once core pieces are validated.

## Running the mover webhook (local)

Prereqs: Python 3.12, `pip install -r scaffold/requirements.txt`.

Env:
```ini
KYLO_DB_DSN_GLOBAL=postgresql://postgres:postgres@localhost:5432/kylo_global
KYLO_DB_DSN_MAP={"company_a":"postgresql://postgres:postgres@localhost:5432/kylo_company_a"}
KYLO_N8N_SIGNATURE_SECRET=
KYLO_N8N_TIMEOUT=15
```

Run:
```bash
uvicorn services.webhook.server:app --host 0.0.0.0 --port 8080
```

Smoke test:
```bash
curl -X POST http://localhost:8080/webhook/kylo/move-batch \
  -H "Content-Type: application/json" \
  -d '{"ingest_batch_id": 1001, "companies": [{"company_id": "company_a"}]}'
```


