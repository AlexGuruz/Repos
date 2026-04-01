#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$SCRIPT_DIR")"

echo ""
echo "  AI Lab · Command Center"
echo "  ────────────────────────"

# Check .env
if [ ! -f "$ROOT/backend/.env" ]; then
  echo "  [warn] No .env found — copying .env.example"
  cp "$ROOT/backend/.env.example" "$ROOT/backend/.env"
fi

# Backend deps
echo "  [1/3] Installing backend deps…"
cd "$ROOT/backend"
pip install -r requirements.txt --quiet

# Frontend deps
echo "  [2/3] Installing frontend deps…"
cd "$ROOT/frontend"
npm install --silent

# Launch both
echo "  [3/3] Starting backend + frontend…"
echo ""
cd "$ROOT/backend"
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!

cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!

echo "  Backend  → http://localhost:8000"
echo "  Frontend → http://localhost:5173"
echo "  WS       → ws://localhost:8000/ws/events"
echo ""
echo "  Press Ctrl+C to stop both."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
