#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

require_installation() {
  if [[ ! -x ".venv/bin/uvicorn" ]]; then
    echo "backend is not installed; run: ./scripts/install.sh" >&2
    exit 1
  fi
}

usage() {
  cat <<'EOF'
Usage: ./scripts/start.sh [options]

Options:
  --foreground       Run backend and frontend in the foreground.
  --background       Run both processes detached with logs in /tmp.
  --host HOST        Backend bind host.   [default: 0.0.0.0]
  --port PORT        Backend bind port.   [default: 80]
  --frontend-port    Frontend bind port.  [default: 5173]
  --help             Show this help.
EOF
}

mode=foreground
backend_host=0.0.0.0
backend_port=80
frontend_port=5173

while [[ $# -gt 0 ]]; do
  case "$1" in
    --foreground|-f)
      mode=foreground
      shift
      ;;
    --background|-b)
      mode=background
      shift
      ;;
    --host|-H)
      backend_host="${2:-}"
      shift 2
      ;;
    --port|-p)
      backend_port="${2:-}"
      shift 2
      ;;
    --frontend-port)
      frontend_port="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$backend_host" || -z "$backend_port" || -z "$frontend_port" ]]; then
  echo "missing host or port" >&2
  usage >&2
  exit 2
fi

require_installation

if [[ "$mode" == "background" ]]; then
  backend_log=""
  frontend_log=""
  nohup .venv/bin/uvicorn mmqp.adapters.fastapi.app:app --host "$backend_host" --port "$backend_port" >"$backend_log" 2>&1 &
  backend_pid=$!
  (
    cd frontend
    nohup npm run dev -- --host --port "$frontend_port" >"$frontend_log" 2>&1
  ) &
  frontend_pid=$!

  echo "backend pid: $backend_pid [log: $backend_log]"
  echo "frontend pid: $frontend_pid [log: $frontend_log]"
  echo "backend: http://$backend_host:$backend_port"
  echo "frontend: http://127.0.0.1:$frontend_port"
  exit 0
fi

BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  [[ -z "$BACKEND_PID" ]] || kill "$BACKEND_PID" 2>/dev/null || true
  [[ -z "$FRONTEND_PID" ]] || kill "$FRONTEND_PID" 2>/dev/null || true
  wait
}

trap cleanup EXIT

.venv/bin/uvicorn mmqp.adapters.fastapi.app:app --host "$backend_host" --port "$backend_port" &
BACKEND_PID=$!

(
  cd frontend
  npm run dev -- --host --port "$frontend_port"
) &
FRONTEND_PID=$!

echo "backend: http://$backend_host:$backend_port"
echo "frontend: http://127.0.0.1:$frontend_port"
wait
