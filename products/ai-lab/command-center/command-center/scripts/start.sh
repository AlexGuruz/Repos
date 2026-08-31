#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"
AI_LAB_ROOT="${AI_LAB_ROOT:-/mnt/workshop/Repos/products/ai-lab}"
export AI_LAB_ROOT
export PYTHONPATH="${AI_LAB_ROOT}${PYTHONPATH:+:$PYTHONPATH}"

echo ""
echo "  AI Lab · Command Center (Linux)"
echo "  ───────────────────────────────"

if [ ! -f "$ROOT/backend/.env" ]; then
  echo "  [warn] No backend/.env — copying .env.example"
  cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"
fi

if command -v docker >/dev/null 2>&1 && [ "${CC_USE_COMPOSE:-1}" = "1" ]; then
  echo "  [compose] docker compose up -d --build"
  (cd "$ROOT" && docker compose up -d --build)
  echo "  UI  → http://127.0.0.1:5173"
  echo "  API → http://127.0.0.1:8000"
  echo "  Health → http://127.0.0.1:8000/api/health"
  echo "  Logs: docker compose -f $ROOT/docker-compose.yml logs -f"
  exit 0
fi

echo "  [1/3] Backend deps…"
cd "$ROOT/backend"
python3 -m pip install -r requirements.txt --quiet

echo "  [2/3] Frontend deps…"
cd "$ROOT/frontend"
npm install --silent

echo "  [3/3] Starting uvicorn + vite…"
cd "$ROOT/backend"
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo "  Backend  → http://127.0.0.1:8000"
echo "  Frontend → http://127.0.0.1:5173"
echo "  Press Ctrl+C to stop."
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
