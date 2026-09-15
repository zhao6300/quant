#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

(
  cd "$ROOT_DIR"
  uv sync --extra dev
  uv run python -c "import mmqp, uvicorn"
)

(
  cd "$ROOT_DIR/frontend"
  npm install
  npm run build
)

echo "install: done"
