#!/usr/bin/env bash
# Launcher for Rob's Solar.app — must work when started from the Dock (minimal PATH).
set -uo pipefail

ROOT="${ROBS_SOLAR_ROOT:-/Users/robertcashman/robs-solar}"
URL="http://127.0.0.1:3000"
LOG="$ROOT/.launch.log"

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

CURL="/usr/bin/curl"
OPEN="/usr/bin/open"
OSASCRIPT="/usr/bin/osascript"
NPM=""

for candidate in /usr/local/bin/npm /opt/homebrew/bin/npm; do
  if [[ -x "$candidate" ]]; then
    NPM="$candidate"
    break
  fi
done
if [[ -z "$NPM" ]]; then
  NPM="$(command -v npm 2>/dev/null || true)"
fi

log() {
  printf '%s %s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$*" >>"$LOG"
}

notify() {
  "$OSASCRIPT" -e "display notification \"$2\" with title \"$1\"" 2>/dev/null || true
}

alert() {
  "$OSASCRIPT" -e "display alert \"$1\" message \"$2\"" 2>/dev/null || true
}

is_up() {
  "$CURL" -s -o /dev/null --connect-timeout 2 "$URL" 2>/dev/null
}

backend_up() {
  "$CURL" -s -o /dev/null --connect-timeout 2 "http://127.0.0.1:8000/health" 2>/dev/null
}

PLIST_SRC="$ROOT/scripts/launchd/com.robssolar.backend.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.robssolar.backend.plist"
AGENT_LABEL="com.robssolar.backend"

ensure_backend_agent() {
  # The backend runs as a launchd service so the OS keeps it alive (KeepAlive).
  # The old approach started uvicorn under the launcher's process group, where it
  # died ~40s after launch and left the UI hitting a dead backend (500s).
  local uid
  uid="$(id -u)"
  if [[ -f "$PLIST_SRC" ]]; then
    mkdir -p "$HOME/Library/LaunchAgents"
    cp "$PLIST_SRC" "$PLIST_DST" 2>/dev/null || true
  fi
  if [[ -f "$PLIST_DST" ]]; then
    launchctl bootstrap "gui/$uid" "$PLIST_DST" 2>/dev/null \
      || launchctl load -w "$PLIST_DST" 2>/dev/null || true
    launchctl kickstart "gui/$uid/$AGENT_LABEL" 2>/dev/null || true
    log "ensured backend launchd agent"
  else
    log "backend plist missing ($PLIST_DST); falling back to dev.sh backend"
  fi
}

needs_build() {
  # Rebuild only when there is no prior build, or when frontend source is newer
  # than the last build. Keeps warm launches instant while staying correct after
  # code changes.
  local build_id="$ROOT/frontend/.next/BUILD_ID"
  [[ -f "$build_id" ]] || return 0
  local newer
  newer="$(find "$ROOT/frontend/src" "$ROOT/frontend/next.config.ts" \
    "$ROOT/frontend/package.json" -newer "$build_id" -print -quit 2>/dev/null)"
  [[ -n "$newer" ]]
}

start_frontend() {
  cd "$ROOT" || exit 1
  if needs_build; then
    notify "Rob's Solar" "Building dashboard (one-time after update)…"
    log "frontend build is stale or missing — running production build"
    bash "$ROOT/scripts/build-frontend.sh" >>"$LOG" 2>&1 || log "frontend build failed"
  else
    log "frontend build is fresh — skipping rebuild"
  fi
  cd "$ROOT/frontend" || exit 1
  if [[ "$(uname -m)" == "arm64" && -x /usr/bin/arch ]]; then
    nohup /usr/bin/arch -arm64 "$NPM" run start -- --port 3000 >>"$LOG" 2>&1 &
  else
    nohup "$NPM" run start -- --port 3000 >>"$LOG" 2>&1 &
  fi
}

start_stack() {
  notify "Rob's Solar" "Starting dashboard servers…"
  log "starting stack (backend agent + frontend)"
  ensure_backend_agent
  if ! is_up; then
    start_frontend
  fi
  for _ in $(seq 1 90); do
    if is_up && backend_up; then
      return 0
    fi
    sleep 1
  done
  return 1
}

log "launch started (PATH=$PATH, npm=${NPM:-missing})"

if [[ -z "$NPM" ]]; then
  log "npm not found"
  alert "Rob's Solar could not start" "Node.js npm was not found. Install Node or check /usr/local/bin/npm."
  exit 1
fi

if ! is_up || ! backend_up; then
  if is_up && ! backend_up; then
    log "frontend up but backend down — (re)starting backend agent"
    ensure_backend_agent
    for _ in $(seq 1 30); do
      backend_up && break
      sleep 1
    done
  fi
  if ! is_up || ! backend_up; then
    start_stack || true
  fi
else
  log "dashboard and backend already running"
fi

if is_up && backend_up; then
  log "opening $URL"
  "$OPEN" "$URL"
  notify "Rob's Solar" "Dashboard opened in your browser"
  exit 0
fi

log "dashboard did not become reachable"
alert "Rob's Solar did not start in time" "Check $LOG for details."
exit 1
