#!/usr/bin/env bash
# Regression checks for the Rob's Finance Mac / local launcher.
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LAUNCH="$ROOT/scripts/mac-launch.sh"
DEV="$ROOT/scripts/dev.sh"
BUILD="$ROOT/scripts/build-mac-app.sh"
WRAPPER="$ROOT/scripts/mac-app-wrapper.sh"
ROOT_SH="$ROOT/scripts/mac-root.sh"
PIN="$ROOT/scripts/pin-rob-finance-dock.py"
APP_BIN="$ROOT/macos/RobsFinance.app/Contents/MacOS/RobsFinance"

fail=0
pass() { printf 'ok   - %s\n' "$1"; }
bad()  { printf 'FAIL - %s\n' "$1" >&2; fail=1; }

if [[ -x "$LAUNCH" ]]; then
  pass "launcher is executable"
else
  bad "missing executable: $LAUNCH"
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "skip - npm Dock PATH check is macOS-only"
else
  found=0
  for candidate in /usr/local/bin/npm /opt/homebrew/bin/npm; do
    if [[ -x "$candidate" ]]; then
      found=1
    fi
  done
  if [[ "$found" -eq 1 ]]; then
    pass "npm discoverable on minimal PATH"
  else
    bad "expected npm at /usr/local/bin/npm or /opt/homebrew/bin/npm"
  fi
fi

CURL_BIN="$(command -v curl 2>/dev/null || echo /usr/bin/curl)"
if "$CURL_BIN" -s -o /dev/null --connect-timeout 2 "http://127.0.0.1:59999" 2>/dev/null; then
  bad "is_up curl check returned success for a closed port"
else
  pass "is_up curl check reports closed port as down"
fi
if grep -Eq -- '-sf? -o /dev/null --connect-timeout' "$LAUNCH"; then
  pass "launcher uses exit-code based health check"
else
  bad "launcher is_up no longer uses the exit-code curl check"
fi
if grep -q 'FRONTEND_PORT:-3000' "$LAUNCH" && grep -q 'open_dashboard' "$LAUNCH"; then
  pass "launcher opens the Rob's Finance dashboard"
else
  bad "launcher no longer opens http://127.0.0.1:3000"
fi
if grep -q "Rob's Finance" "$LAUNCH"; then
  pass "launcher branding is Rob's Finance"
else
  bad "launcher still says Rob's Solar"
fi

if grep -Eq 'arch -arm64[^\n]*uvicorn' "$DEV"; then
  pass "dev.sh pins uvicorn to arm64"
else
  bad "dev.sh no longer pins uvicorn to arm64 (arch mismatch risk)"
fi

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

if grep -q 'already running' "$LAUNCH" && grep -q 'looks_like_robs_finance' "$LAUNCH"; then
  pass "launcher reuses a running Rob's Finance instance"
else
  bad "launcher missing reuse-existing-instance guard"
fi
# shellcheck source=mac-root.sh
source "$ROOT_SH"
PLIST="$ROOT/scripts/launchd/com.robssolar.backend.plist"
plist_value_after() {
  local file="$1" key="$2"
  awk -v key="$key" '
    $0 ~ "<key>" key "</key>" {
      getline
      while ($0 ~ /<!--/ || $0 ~ /^[[:space:]]*$/) getline
      gsub(/^[[:space:]]+|[[:space:]]+$/, "")
      print
      exit
    }
  ' "$file"
}
generated_plist="$(mktemp)"
write_backend_launch_agent "$ROOT" "$generated_plist"
if [[ "$(plist_value_after "$ROOT_SH" RunAtLoad)" == "<false/>" ]] \
  && [[ "$(plist_value_after "$ROOT_SH" KeepAlive)" == "<false/>" ]] \
  && [[ "$(plist_value_after "$PLIST" RunAtLoad)" == "<false/>" ]] \
  && [[ "$(plist_value_after "$PLIST" KeepAlive)" == "<false/>" ]] \
  && [[ "$(plist_value_after "$generated_plist" RunAtLoad)" == "<false/>" ]] \
  && [[ "$(plist_value_after "$generated_plist" KeepAlive)" == "<false/>" ]] \
  && ! grep -q '<key>Crashed</key>' "$ROOT_SH" \
  && ! grep -q '<key>Crashed</key>' "$PLIST" \
  && ! grep -q '<key>Crashed</key>' "$generated_plist" \
  && grep -q 'KeepAlive=false' "$LAUNCH" \
  && grep -q 'launchctl bootout' "$LAUNCH"; then
  pass "backend launch agent does not start at macOS login"
else
  bad "backend launch agent still has login auto-start (KeepAlive must be false)"
fi
rm -f "$generated_plist"
if grep -q 'pin-rob-finance-dock.py' "$BUILD" \
  && grep -q 'app_already_installed' "$BUILD" \
  && grep -q '_tile_points_at_app' "$PIN" \
  && ! grep -E '^[[:space:]]*dockutil[[:space:]]+--add' "$BUILD" \
  && ! grep -E '^[[:space:]]*killall[[:space:]]+Dock' "$BUILD"; then
  pass "Mac installer pins Dock idempotently (no Dock restart on every open)"
else
  bad "build-mac-app.sh Dock pin is not idempotent"
fi
if grep -q 'install_desktop_shortcuts' "$BUILD" \
  && grep -q 'place_visible_app_symlink' "$BUILD" \
  && grep -q 'RobsFinance.command' "$BUILD" \
  && grep -q 'place_visible_shortcut' "$BUILD" \
  && grep -q 'remove_stale_desktop_launchers' "$BUILD" \
  && [[ -f "$ROOT/scripts/desktop-robs-finance.command" ]] \
  && [[ -f "$ROOT/scripts/open-rob-finance-app.command" ]] \
  && [[ -f "$ROOT/scripts/visible-desktop.sh" ]] \
  && grep -q 'RobsFinance.app' "$ROOT/scripts/desktop-robs-finance.command" \
  && grep -q 'https://robs-solar.vercel.app' "$ROOT/scripts/desktop-robs-finance.command" \
  && ! grep -q 'cursor/robs-finance-mac-run' "$ROOT/scripts/desktop-robs-finance.command"; then
  pass "Mac installer restores the Desktop RobsFinance.app shortcut"
else
  bad "build-mac-app.sh no longer restores the Desktop app shortcut"
fi
if grep -q 'https://robs-solar.vercel.app' "$ROOT/scripts/mac-app-wrapper.sh" \
  && grep -q 'https://robs-solar.vercel.app' "$ROOT/macos/RobsFinance.app/Contents/MacOS/RobsFinance" \
  && grep -q 'open_hosted_robs_finance' "$ROOT_SH"; then
  pass "Dock and Desktop icons open the live site when the local app is missing"
else
  bad "Mac launchers still bounce instead of opening the live Finance site"
fi
INSTALLER="$ROOT/scripts/install-mac-website-shortcut.sh"
PUBLIC_INSTALLER="$ROOT/frontend/public/install-mac-shortcut.sh"
if [[ -x "$INSTALLER" && -f "$PUBLIC_INSTALLER" ]] \
  && cmp -s "$INSTALLER" "$PUBLIC_INSTALLER" \
  && [[ -f "$ROOT/frontend/public/pin-rob-finance-dock.py" ]]; then
  pass "hosted Mac installer is published at /install-mac-shortcut.sh"
else
  bad "hosted Mac installer is missing or out of date in frontend/public"
fi
if [[ -x "$INSTALLER" ]]; then
  TEST_HOME="$(mktemp -d)"
  if INSTALL_MAC_SHORTCUT_TEST=1 HOME="$TEST_HOME" bash "$INSTALLER" >/tmp/install-mac-website-shortcut.log 2>&1 \
    && [[ -x "$TEST_HOME/Applications/RobsFinance.app/Contents/MacOS/RobsFinance" ]] \
    && grep -q 'https://robs-solar.vercel.app/login?send=1' "$TEST_HOME/Applications/RobsFinance.app/Contents/MacOS/RobsFinance" \
    && [[ -x "$TEST_HOME/Desktop/RobsFinance.command" ]] \
    && ! grep -q '127.0.0.1:3000' "$TEST_HOME/Applications/RobsFinance.app/Contents/MacOS/RobsFinance"; then
  pass "website Mac installer creates RobsFinance.app without localhost"
  else
    bad "website Mac installer failed (see /tmp/install-mac-website-shortcut.log)"
  fi
  rm -rf "$TEST_HOME"
else
  bad "missing executable: $INSTALLER"
fi
if [[ -f "$ROOT/frontend/public/RobsFinance.url" ]] \
  && grep -q 'https://robs-solar.vercel.app/login?send=1' "$ROOT/frontend/public/RobsFinance.url" \
  && [[ -f "$ROOT/frontend/public/install-windows-shortcut.ps1" ]]; then
  pass "Windows Desktop shortcut opens hosted login"
else
  bad "Windows internet shortcut is missing"
fi
if grep -q 'foreign_port_message' "$LAUNCH"; then
  pass "launcher detects a foreign process on the app ports"
else
  bad "launcher missing foreign-port detection"
fi
if grep -q 'frontend up but backend down' "$LAUNCH" && grep -q 'backend_up' "$LAUNCH"; then
  pass "launcher restarts stack when backend is down"
else
  bad "launcher missing backend-down restart guard"
fi

if grep -q 'rm -rf "$ROOT/frontend/.next"' "$LAUNCH"; then
  bad "launcher still wipes .next on every launch (forces cold start)"
else
  pass "launcher no longer wipes .next"
fi
if grep -Eq 'run start -- --port' "$LAUNCH"; then
  pass "launcher serves production build (next start)"
else
  bad "launcher no longer starts the frontend in production mode (next start)"
fi
if [[ -x "$ROOT/scripts/build-frontend.sh" ]]; then
  pass "build-frontend.sh exists and is executable"
else
  bad "missing executable: $ROOT/scripts/build-frontend.sh"
fi

if grep -q 'All/robs-solar' "$LAUNCH" && grep -q 'HOME/All/robs-solar' "$LAUNCH"; then
  pass "launcher prefers All monorepo checkout over old standalone clone"
else
  bad "launcher still hardcodes only /Users/robertcashman/robs-solar"
fi
if grep -q 'looks_like_energy_build' "$LAUNCH" && grep -q 'stop_stale_stack' "$LAUNCH" \
  && grep -q 'leftover Energy build still present after stop' "$LAUNCH" \
  && grep -q 'refusing to open leftover Energy build after launch' "$LAUNCH" \
  && grep -Fq '(! looks_like_robs_finance || looks_like_energy_build)' "$LAUNCH"; then
  pass "launcher stops a leftover Energy localhost build instead of reusing it"
else
  bad "launcher can still reuse an old Energy server on port 3000"
fi
if grep -q 'frontend/src/app/(energy)' "$ROOT/scripts/mac-root.sh"; then
  pass "path resolver rejects old Energy checkouts"
else
  bad "mac-root.sh still accepts standalone trees that contain Energy pages"
fi

if [[ -x "$BUILD" ]] && grep -q 'APP_DIR=.*RobsFinance.app' "$BUILD" && ! grep -q 'APP_DIR=.*Rob'\''s Finance.app' "$BUILD"; then
  pass "Mac builder installs RobsFinance.app (no apostrophe in path)"
else
  bad "build-mac-app.sh does not install RobsFinance.app without an apostrophe"
fi
if grep -q "CFBundleDisplayName" "$BUILD" && grep -q "Rob's Finance" "$BUILD"; then
  pass "installed app display name is Rob's Finance"
else
  bad "build-mac-app.sh missing CFBundleDisplayName Rob's Finance"
fi
if [[ -x "$WRAPPER" ]] && grep -q 'mac-launch.sh' "$WRAPPER"; then
  pass "Dock wrapper execs the latest checkout launcher"
else
  bad "missing thin Dock wrapper that execs mac-launch.sh"
fi
if [[ -x "$APP_BIN" ]] && grep -q 'mac-launch.sh' "$APP_BIN"; then
  pass "macOS app template exists at macos/RobsFinance.app"
else
  bad "missing macos/RobsFinance.app launcher"
fi
if grep -q 'getByLabel("Email")' "$ROOT/frontend/e2e/helpers.ts"; then
  pass "e2e login setup uses the Email field"
else
  bad "e2e login helpers still look for Username"
fi
if [[ -f "$ROOT/scripts/assets/rob-finance-icon.png" ]]; then
  pass "Rob's Finance Dock icon is in the repo"
else
  bad "missing scripts/assets/rob-finance-icon.png"
fi

resolved="$(ROBS_SOLAR_ROOT="$ROOT" resolve_robs_solar_root || true)"
if [[ "$resolved" == "$ROOT" ]]; then
  pass "resolve_robs_solar_root uses ROBS_SOLAR_ROOT"
else
  bad "resolve_robs_solar_root ignored ROBS_SOLAR_ROOT (got: $resolved)"
fi

LOG_DIR="$(robs_finance_log_dir)"
if [[ "$LOG_DIR" == *"/Library/Logs/RobsFinance" || "$LOG_DIR" == *"/robs-finance/logs" ]]; then
  pass "launcher log directory is RobsFinance logs"
else
  bad "unexpected log directory: $LOG_DIR"
fi

if [[ -f "$PIN" ]]; then
  if python3 "$PIN" --self-test >/dev/null; then
    pass "Dock pin URL has no apostrophe and keeps slashes"
  else
    bad "Dock pin URL self-test failed"
  fi
else
  bad "missing pin-rob-finance-dock.py"
fi

if grep -q 'Library/Logs/RobsFinance' "$LAUNCH"; then
  pass "launcher writes ~/Library/Logs/RobsFinance"
else
  bad "launcher no longer logs to ~/Library/Logs/RobsFinance"
fi

FREE_PORTS="$ROOT/scripts/free-dev-ports.py"
if [[ -f "$FREE_PORTS" ]] && grep -q 'free-dev-ports.py' "$ROOT/scripts/verify.sh"; then
  if python3 "$FREE_PORTS" --self-test >/dev/null; then
    pass "verify frees leftover Next/API listeners before e2e"
  else
    bad "free-dev-ports self-test failed"
  fi
else
  bad "verify.sh no longer uses scripts/free-dev-ports.py"
fi

# Live reuse test when the stack is already up.
if "$CURL_BIN" -sf -o /dev/null "http://127.0.0.1:3000/login" 2>/dev/null \
  && "$CURL_BIN" -sf -o /dev/null "http://127.0.0.1:8000/health" 2>/dev/null; then
  if env -i HOME="$HOME" USER="${USER:-}" PATH="/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}" \
      ROBS_SOLAR_ROOT="$ROOT" ROBS_FINANCE_SKIP_OPEN=1 bash "$LAUNCH"; then
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
