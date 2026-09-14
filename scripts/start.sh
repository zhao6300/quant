#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  [[ -z "$BACKEND_PID" ]] || kill "$BACKEND_PID" 2>/dev/null || true
  [[ -z "$FRONTEND_PID" ]] || kill "$FRONTEND_PID" 2>/dev/null || true
  wait
}

trap cleanup EXIT

.venv/bin/uvicorn mmqp.adapters.fastapi.app:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

(
  cd frontend
  npm run dev
) &
FRONTEND_PID=$!

echo "backend: http://127.0.0.1:8000"
echo "frontend: http://127.0.0.1:5173"
wait
