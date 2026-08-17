#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Backend: ruff"
cd backend
source .venv/bin/activate
ruff check .
echo "==> Backend: pytest"
pytest -q
echo "==> Backend: bandit (high severity only)"
bandit -r app -ll -q || true
echo "==> Backend: pip-audit"
pip-audit || true
cd "$ROOT"

echo "==> Frontend: lint"
cd frontend
npm run lint
echo "==> Frontend: typecheck"
npm run typecheck
echo "==> Frontend: unit tests"
npm run test
echo "==> Frontend: e2e tests"
# E2e starts its own backend on :8000 — stop the launchd service if running.
UID_NUM="$(id -u)"
launchctl bootout "gui/${UID_NUM}/com.robssolar.backend" 2>/dev/null || true
# lsof misses IPv6 Next listeners on some Linux agents and can match Chrome
# client sockets. Only stop processes that own a LISTEN socket.
python3 "$ROOT/scripts/free-dev-ports.py" 8000 3000
sleep 1
CI=true npm run test:e2e
echo "==> Frontend: npm audit"
npm audit --audit-level=high || true
cd "$ROOT"

echo "==> Mac launcher: PATH smoke test"
bash scripts/test-mac-launch.sh

echo "==> All verification checks completed."
