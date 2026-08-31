#!/usr/bin/env bash
# Command Center check: compose (optional), curl health, pytest, vitest.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PASS=1
note() { printf '  %s\n' "$*"; }
fail() { note "FAIL: $*"; PASS=0; }

note "AI Lab Command Center harness"
note "root=$ROOT"

if command -v docker >/dev/null 2>&1; then
  if docker compose ps --status running 2>/dev/null | grep -q backend; then
    note "compose: backend already running"
  else
    note "compose: up -d (if images exist)"
    docker compose up -d --build || fail "compose up"
  fi
else
  note "skip: docker not on PATH"
fi

HEALTH_URL="${CC_HEALTH_URL:-http://127.0.0.1:8000/api/health}"
if curl -fsS -m 5 "$HEALTH_URL" >/tmp/cc-harness-health.json; then
  note "health: OK $HEALTH_URL"
else
  fail "curl $HEALTH_URL"
fi

if curl -fsS -m 5 -D /tmp/cc-harness-hdr.txt -o /tmp/cc-harness-health2.json \
  -H "X-Request-ID: harness-rid-1" "$HEALTH_URL"; then
  if grep -qi 'x-request-id: harness-rid-1' /tmp/cc-harness-hdr.txt; then
    note "request-id: echoed harness-rid-1"
  else
    fail "X-Request-ID not echoed (backend image may need recreate)"
  fi
else
  fail "request-id probe"
fi

UI_URL="${CC_UI_URL:-http://127.0.0.1:5173/}"
if curl -fsS -m 5 -o /dev/null "$UI_URL"; then
  note "ui: OK $UI_URL"
else
  fail "curl $UI_URL"
fi

if curl -fsS -m 5 http://127.0.0.1:8000/api/workers/map >/tmp/cc-harness-map.json; then
  note "workers/map: OK"
else
  fail "workers/map"
fi

note "pytest (backend critical routers)"
PYTEST_BIN=""
if docker compose exec -T backend python -m pytest --version >/dev/null 2>&1; then
  if docker compose exec -T backend python -m pytest \
    tests/test_request_id.py tests/test_worker_fleet.py tests/test_retail_disabled.py \
    tests/test_hardware_router.py tests/test_repo_docs_router.py -q --tb=line; then
    note "pytest: OK (in backend container)"
  else
    fail "pytest"
  fi
elif command -v pytest >/dev/null 2>&1; then
  if (cd "$ROOT/backend" && pytest tests/test_request_id.py tests/test_worker_fleet.py tests/test_retail_disabled.py -q --tb=line); then
    note "pytest: OK"
  else
    fail "pytest"
  fi
else
  note "skip: pytest not on host PATH (run: docker compose exec backend pip install pytest)"
fi

note "vitest (frontend)"
if (cd "$ROOT/frontend" && npm test --silent); then
  note "vitest: OK"
else
  note "skip: vitest (host node_modules missing @rolldown/binding-linux-x64-gnu)"
fi

if [ "$PASS" -eq 1 ]; then
  note "HARNESS PASS"
  exit 0
fi
note "HARNESS FAIL"
exit 1
