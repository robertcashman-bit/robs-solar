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
for _port in 8000 3000; do
  lsof -ti "tcp:${_port}" 2>/dev/null | xargs -r kill -9 2>/dev/null || true
done
sleep 1
CI=true npm run test:e2e
echo "==> Frontend: npm audit"
npm audit --audit-level=high || true
cd "$ROOT"

echo "==> Mac launcher: PATH smoke test"
bash scripts/test-mac-launch.sh

echo "==> All verification checks completed."
