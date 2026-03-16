# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

Multi-system financial operations monorepo for cannabis industry holding companies. The core product is **Project-Kylo** — an automated financial processing pipeline (CSV intake → PostgreSQL → Google Sheets). See `docs/SYSTEMS_OVERVIEW.md` and `Project-Kylo/docs/README.md` for architecture details.

### Services

| Service | How to start | Port | Notes |
|---------|-------------|------|-------|
| PostgreSQL 16 | `docker compose up -d` (from `Project-Kylo/`) | 5433 | Requires `docker network create remodel_default` first |
| FastAPI Webhook API | `python3 -m uvicorn services.webhook.server:app --host 0.0.0.0 --port 8000` (from `Project-Kylo/`) | 8000 | Set `KYLO_DB_DSN_GLOBAL` and `KYLO_DB_DSN_MAP` env vars; see `scaffold/example.env` |
| Kylo Dashboard (Vite) | `npx vite --host 0.0.0.0` (from `Project-Kylo/kylo-dashboard/`) | 5173 | Electron app; renders blank in browser (needs `window.electronAPI`) |
| Redpanda (Kafka) | `docker compose -f docker-compose.kafka.yml up -d` (from `Project-Kylo/`) | 9092 | Optional for dev unless testing Kafka consumers |

### Running tests

```bash
cd Project-Kylo

# Unit tests (no DB needed)
python3 -m pytest -m "not integration" -q

# Integration tests (requires PostgreSQL running with test DBs)
python3 -m pytest -m "integration" -q

# Specific test suites (from CI)
python3 -m pytest scaffold/tests/sheets/test_poster.py -q
python3 -m pytest scaffold/tests/mover/test_rules_snapshot.py -m integration -q
```

### Database setup for integration tests

After starting PostgreSQL via `docker compose up -d`:

```bash
docker exec kylo-pg createdb -U postgres kylo_global
docker exec kylo-pg createdb -U postgres kylo_company_a
docker exec kylo-pg createdb -U postgres kylo_company_b

# Apply DDLs
for f in 0002_core_intake_control.sql 0003_helpers.sql 0004_control_rules_version.sql 0005_control_mover_runs.sql; do
  docker cp db/ddl/$f kylo-pg:/ && docker exec kylo-pg psql -U postgres -d kylo_global -f /$f
done

for db in kylo_company_a kylo_company_b; do
  docker cp db/ddl/company_0001_app.sql kylo-pg:/ && docker exec kylo-pg psql -U postgres -d $db -f /company_0001_app.sql
done
```

### Non-obvious gotchas

- **Docker network**: The `remodel_default` Docker network must exist before starting any compose service. Create it with `docker network create remodel_default`.
- **PostgreSQL port**: Docker maps to port **5433** (not 5432). The test `conftest.py` defaults to `localhost:5433`.
- **`psycopg` vs `psycopg2`**: The main `requirements.txt` uses `psycopg2-binary`, but `scaffold/tests/mover/test_rules_snapshot.py` imports `psycopg` (v3). Install both: `pip install psycopg2-binary "psycopg[binary]"`.
- **Dashboard devDependencies**: The `kylo-dashboard/package.json` is missing devDependencies. You need to install: `npm install --save-dev vite @vitejs/plugin-react typescript tailwindcss@3 autoprefixer postcss @types/react @types/react-dom`.
- **Some integration tests have pre-existing failures**: The triage tests (`scaffold/tests/triage/`) and some mover tests fail with assertion errors unrelated to environment setup. The core unit tests (39 tests) and rules snapshot integration test pass cleanly.
- **Google Sheets API**: Full end-to-end operations require a `service_account.json` file. Without it, the system runs in dry-run mode (`KYLO_SHEETS_DRY_RUN=true`).
