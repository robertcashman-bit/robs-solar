#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

cleanup() {
  trap - INT TERM
  kill 0 2>/dev/null || true
}
trap cleanup INT TERM

echo "Starting Rob's Solar backend on :8000..."
# Hot-reload is opt-in: it is unstable under the detached Dock launcher, so the
# default is a single stable process. Set ROBS_SOLAR_RELOAD=1 for dev reload.
RELOAD_FLAG=""
if [[ "${ROBS_SOLAR_RELOAD:-0}" == "1" ]]; then
  RELOAD_FLAG="--reload"
fi
(
  cd backend
  source .venv/bin/activate
  # Pin to native arch so universal Python loads wheels matching the installed
  # native extensions (e.g. pydantic_core). Dock launches can default to x86_64.
  if [[ "$(uname -m)" == "arm64" && -x /usr/bin/arch ]]; then
    exec /usr/bin/arch -arm64 uvicorn app.main:app $RELOAD_FLAG --host 127.0.0.1 --port 8000
  else
    exec uvicorn app.main:app $RELOAD_FLAG --host 127.0.0.1 --port 8000
  fi
) &

echo "Starting Rob's Solar frontend on :3000..."
(
  cd frontend
  if [[ "$(uname -m)" == "arm64" && -x /usr/bin/arch ]]; then
    exec /usr/bin/arch -arm64 npm run dev -- --port 3000
  else
    exec npm run dev -- --port 3000
  fi
) &

wait
