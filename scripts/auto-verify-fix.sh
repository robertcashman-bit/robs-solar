#!/usr/bin/env bash
# Run scripts/verify.sh in a loop until green or max attempts reached.
# Usage: bash scripts/auto-verify-fix.sh [max_attempts]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MAX_ATTEMPTS="${1:-5}"
ATTEMPT=1

echo "Auto-verify: up to ${MAX_ATTEMPTS} attempt(s) targeting scripts/verify.sh"
echo "Fix failures manually or with an agent between attempts."
echo

while [[ "$ATTEMPT" -le "$MAX_ATTEMPTS" ]]; do
  echo "========== Attempt ${ATTEMPT}/${MAX_ATTEMPTS} =========="
  if bash "$ROOT/scripts/verify.sh"; then
    echo
    echo "Auto-verify: COMPLETE (green on attempt ${ATTEMPT})"
    exit 0
  fi
  echo
  echo "Auto-verify: attempt ${ATTEMPT} failed."
  if [[ "$ATTEMPT" -eq "$MAX_ATTEMPTS" ]]; then
    echo "Auto-verify: STOPPED after ${MAX_ATTEMPTS} attempts — fix remaining issues and re-run."
    exit 1
  fi
  echo "Re-run after fixes (waiting 2s)..."
  sleep 2
  ATTEMPT=$((ATTEMPT + 1))
done
