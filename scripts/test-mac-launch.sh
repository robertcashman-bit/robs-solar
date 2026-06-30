#!/usr/bin/env bash
# Regression checks for the Rob's Solar Mac launcher.
#
# These guard the failure modes we actually hit when launching from the Dock:
#   1. npm not on a minimal (Dock) PATH
#   2. is_up() reporting a down port as "up" (the curl exit-code bug)
#   3. backend running under the wrong CPU arch (x86_64 vs arm64)
#   4. lightningcss/oxide native binary missing -> 500 on first paint
#   5. launcher not restarting when the frontend is up but the backend is down
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCH="$ROOT/scripts/mac-launch.sh"
DEV="$ROOT/scripts/dev.sh"

fail=0
pass() { printf 'ok   - %s\n' "$1"; }
bad()  { printf 'FAIL - %s\n' "$1" >&2; fail=1; }

# --- 0. launcher exists and is executable ------------------------------------
if [[ -x "$LAUNCH" ]]; then
  pass "launcher is executable"
else
  bad "missing executable: $LAUNCH"
fi

# --- 1. npm discoverable under a Dock-like minimal PATH ----------------------
if env -i HOME="$HOME" USER="${USER:-}" PATH="/usr/bin:/bin:/usr/sbin:/sbin" bash -c '
  for candidate in /usr/local/bin/npm /opt/homebrew/bin/npm; do
    [[ -x "$candidate" ]] && exit 0
  done
  exit 1
'; then
  pass "npm discoverable on minimal PATH"
else
  bad "expected npm at /usr/local/bin/npm or /opt/homebrew/bin/npm"
fi

# --- 2. is_up() must treat a closed port as DOWN -----------------------------
# Regression for the bug where curl's string output made a down server look up.
# Mirror the launcher's check verbatim against a port nothing is listening on.
if /usr/bin/curl -s -o /dev/null --connect-timeout 2 "http://127.0.0.1:59999" 2>/dev/null; then
  bad "is_up curl check returned success for a closed port"
else
  pass "is_up curl check reports closed port as down"
fi
if grep -q -- '-s -o /dev/null --connect-timeout' "$LAUNCH"; then
  pass "launcher uses exit-code based health check"
else
  bad "launcher is_up no longer uses the exit-code curl check"
fi

# --- 3. backend pinned to native arch in dev.sh ------------------------------
if grep -Eq 'arch -arm64[^\n]*uvicorn' "$DEV"; then
  pass "dev.sh pins uvicorn to arm64"
else
  bad "dev.sh no longer pins uvicorn to arm64 (arch mismatch risk)"
fi

# --- 4. native CSS binaries resolve for the running arch ---------------------
NODE="$(command -v node 2>/dev/null || true)"
if [[ -n "$NODE" ]]; then
  ( cd "$ROOT/frontend" && "$NODE" -e 'require("lightningcss")' ) >/dev/null 2>&1 \
    && pass "lightningcss native module loads" \
    || bad "lightningcss native module failed to load (run scripts/ensure-lightningcss.sh)"
  ( cd "$ROOT/frontend" && "$NODE" -e 'require("@tailwindcss/oxide")' ) >/dev/null 2>&1 \
    && pass "@tailwindcss/oxide native module loads" \
    || bad "@tailwindcss/oxide native module failed to load (run scripts/ensure-lightningcss.sh)"
else
  echo "skip - node not on PATH; cannot verify native CSS modules"
fi

# --- 5. launcher restarts when frontend is up but backend is down ------------
if grep -q 'frontend up but backend down' "$LAUNCH" && grep -q 'backend_up' "$LAUNCH"; then
  pass "launcher restarts stack when backend is down"
else
  bad "launcher missing backend-down restart guard"
fi

# --- 5b. launcher serves a cached production build (fast warm start) ---------
# Regression for the slow-launch bug: it used to wipe .next and run `next dev`,
# forcing a cold compile on every open.
if grep -q 'rm -rf "$ROOT/frontend/.next"' "$LAUNCH"; then
  bad "launcher still wipes .next on every launch (forces cold start)"
else
  pass "launcher no longer wipes .next"
fi
if grep -Eq 'run start -- --port 3000' "$LAUNCH"; then
  pass "launcher serves production build (next start)"
else
  bad "launcher no longer starts the frontend in production mode (next start)"
fi
if [[ -x "$ROOT/scripts/build-frontend.sh" ]]; then
  pass "build-frontend.sh exists and is executable"
else
  bad "missing executable: $ROOT/scripts/build-frontend.sh"
fi

# --- 6. dry-run: don't crash when the stack is already up --------------------
if /usr/bin/curl -sf -o /dev/null "http://127.0.0.1:3000/" 2>/dev/null; then
  if env -i HOME="$HOME" USER="${USER:-}" PATH="/usr/bin:/bin:/usr/sbin:/sbin" \
      ROBS_SOLAR_ROOT="$ROOT" bash "$LAUNCH"; then
    pass "launcher dry-run ok (dashboard already running)"
  else
    bad "launcher dry-run crashed while dashboard was running"
  fi
else
  echo "skip - dashboard not running; skipped live open test"
fi

if [[ "$fail" -ne 0 ]]; then
  echo "mac-launch checks FAILED" >&2
  exit 1
fi
echo "mac-launch checks passed"
