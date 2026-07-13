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
  # --max-time guards against a zombie server that holds the port but never
  # responds; without it this call (and the whole launcher) would hang forever
  # and the Dock icon would appear to do nothing.
  "$CURL" -s -o /dev/null --connect-timeout 2 --max-time 5 "$URL" 2>/dev/null
}

backend_up() {
  "$CURL" -s -o /dev/null --connect-timeout 2 --max-time 5 "http://127.0.0.1:8000/health" 2>/dev/null
}

clear_hung_frontend() {
  # If something is listening on :3000 but is_up() fails, it is a hung/zombie
  # next-server. Kill it so the frontend agent can bind the port cleanly.
  local pids
  pids="$(lsof -nP -iTCP:3000 -sTCP:LISTEN -t 2>/dev/null || true)"
  [[ -z "$pids" ]] && return 0
  if is_up; then
    return 0
  fi
  log "port 3000 held by unresponsive process(es) [$pids] — killing"
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
  for _ in $(seq 1 5); do
    lsof -nP -iTCP:3000 -sTCP:LISTEN -t >/dev/null 2>&1 || return 0
    sleep 1
  done
  # shellcheck disable=SC2086
  kill -9 $pids 2>/dev/null || true
  sleep 1
}

PLIST_SRC="$ROOT/scripts/launchd/com.robssolar.backend.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.robssolar.backend.plist"
AGENT_LABEL="com.robssolar.backend"

FE_PLIST_SRC="$ROOT/scripts/launchd/com.robssolar.frontend.plist"
FE_PLIST_DST="$HOME/Library/LaunchAgents/com.robssolar.frontend.plist"
FE_AGENT_LABEL="com.robssolar.frontend"

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

ensure_frontend_agent() {
  # The frontend also runs as a launchd service (KeepAlive) so it survives sleep,
  # crashes, and this launcher exiting. Previously it was a fire-and-forget
  # `nohup npm run start &`, which vanished with its parent process group and
  # left the cached PWA shell throwing "Failed to fetch" on every /backend call.
  local uid
  uid="$(id -u)"
  if [[ -f "$FE_PLIST_SRC" ]]; then
    mkdir -p "$HOME/Library/LaunchAgents"
    cp "$FE_PLIST_SRC" "$FE_PLIST_DST" 2>/dev/null || true
  fi
  if [[ -f "$FE_PLIST_DST" ]]; then
    launchctl bootstrap "gui/$uid" "$FE_PLIST_DST" 2>/dev/null \
      || launchctl load -w "$FE_PLIST_DST" 2>/dev/null || true
    launchctl kickstart "gui/$uid/$FE_AGENT_LABEL" 2>/dev/null || true
    log "ensured frontend launchd agent"
  else
    log "frontend plist missing ($FE_PLIST_DST)"
  fi
}

restart_frontend_agent() {
  # Force a restart (kill + relaunch) so a freshly rebuilt bundle is served.
  local uid
  uid="$(id -u)"
  launchctl kickstart -k "gui/$uid/$FE_AGENT_LABEL" 2>/dev/null || true
  log "restarted frontend launchd agent"
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
  # Clear any hung server holding :3000, rebuild if source changed, then hand
  # off to the launchd-supervised frontend agent (which owns `next start`).
  clear_hung_frontend
  cd "$ROOT" || exit 1
  local rebuilt=0
  if needs_build; then
    notify "Rob's Solar" "Building dashboard (one-time after update)…"
    log "frontend build is stale or missing — running production build"
    bash "$ROOT/scripts/build-frontend.sh" >>"$LOG" 2>&1 || log "frontend build failed"
    rebuilt=1
  else
    log "frontend build is fresh — skipping rebuild"
  fi
  ensure_frontend_agent
  if [[ "$rebuilt" == "1" ]]; then
    # Restart so the agent serves the bundle we just rebuilt.
    restart_frontend_agent
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
  # Both services are supervised by launchd, so they are normally already up.
  # If the frontend source changed since the last build, rebuild and restart the
  # agent so the user is never left staring at a stale bundle.
  if needs_build; then
    notify "Rob's Solar" "Updating dashboard to the latest build…"
    log "serving a stale build — rebuilding and restarting frontend agent"
    ( cd "$ROOT" && bash "$ROOT/scripts/build-frontend.sh" >>"$LOG" 2>&1 ) \
      || log "frontend build failed"
    ensure_frontend_agent
    restart_frontend_agent
    for _ in $(seq 1 90); do
      is_up && break
      sleep 1
    done
  fi
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
