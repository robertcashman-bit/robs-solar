#!/usr/bin/env bash
# Launcher for Rob's Finance — Dock .app or local click.
# Must work with a minimal Dock PATH. Does not start at login.
set -uo pipefail

_THIS="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$_THIS/mac-root.sh" ]]; then
  # shellcheck source=mac-root.sh
  source "$_THIS/mac-root.sh"
fi

if [[ -d "$_THIS/../backend" && -d "$_THIS/../frontend" ]]; then
  ROOT="$(cd "$_THIS/.." && pwd)"
elif command -v resolve_robs_solar_root >/dev/null 2>&1; then
  ROOT="$(resolve_robs_solar_root || true)"
fi
ROOT="${ROOT:-${ROBS_SOLAR_ROOT:-$HOME/All/robs-solar}}"
if [[ ! -d "$ROOT/backend" ]]; then
  ROOT="${ROBS_SOLAR_ROOT:-$HOME/robs-solar}"
fi

HOST="127.0.0.1"
FRONTEND_PORT="${ROBS_FINANCE_FRONTEND_PORT:-3000}"
BACKEND_PORT="${ROBS_FINANCE_BACKEND_PORT:-8000}"
URL="http://${HOST}:${FRONTEND_PORT}/"
LOGIN_URL="http://${HOST}:${FRONTEND_PORT}/login"
HEALTH_URL="http://${HOST}:${BACKEND_PORT}/health"

if command -v robs_finance_log_dir >/dev/null 2>&1; then
  LOG_DIR="$(robs_finance_log_dir)"
else
  LOG_DIR="${HOME}/Library/Logs/RobsFinance"
fi
mkdir -p "$LOG_DIR" 2>/dev/null || LOG_DIR="$ROOT"
LOG="$LOG_DIR/launcher.log"
SERVER_LOG="$LOG_DIR/server.log"
FRONTEND_PID_FILE="$LOG_DIR/frontend.pid"
BACKEND_PID_FILE="$LOG_DIR/backend.pid"

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
export ROBS_SOLAR_ROOT="$ROOT"

CURL="$(command -v curl 2>/dev/null || echo /usr/bin/curl)"
OPEN="$(command -v open 2>/dev/null || true)"
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
if [[ -z "$NPM" ]]; then
  for candidate in "$HOME/.nvm/versions/node/"*/bin/npm; do
    if [[ -x "$candidate" ]]; then
      NPM="$candidate"
    fi
  done
fi
if [[ -n "$NPM" ]]; then
  export PATH="$(dirname "$NPM"):$PATH"
fi

log() {
  mkdir -p "$(dirname "$LOG")" 2>/dev/null || true
  printf '%s %s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")" "$*" >>"$LOG"
}

notify() {
  if [[ -x "$OSASCRIPT" ]]; then
    "$OSASCRIPT" -e "display notification \"$2\" with title \"$1\"" 2>/dev/null || true
  fi
}

alert() {
  if [[ -x "$OSASCRIPT" ]]; then
    "$OSASCRIPT" -e "display alert \"$1\" message \"$2\"" 2>/dev/null || true
  else
    printf '%s: %s\n' "$1" "$2" >&2
  fi
}

http_ok() {
  "$CURL" -sf -o /dev/null --connect-timeout 2 "$1" 2>/dev/null
}

is_up() {
  http_ok "$URL" || http_ok "$LOGIN_URL"
}

backend_up() {
  http_ok "$HEALTH_URL"
}

page_body() {
  local body
  body="$("$CURL" -s --connect-timeout 2 "$URL" 2>/dev/null || true)"
  if [[ -z "$body" ]]; then
    body="$("$CURL" -s --connect-timeout 2 "$LOGIN_URL" 2>/dev/null || true)"
  fi
  printf '%s' "$body"
}

looks_like_energy_build() {
  local body
  body="$(page_body)"
  [[ "$body" == *"/energy"* || "$body" == *"Energy / Solar"* || "$body" == *"AI assistant"* ]]
}

looks_like_robs_finance() {
  local body
  body="$(page_body)"
  [[ "$body" == *"Rob's Finance"* || "$body" == *"Robs Finance"* || "$body" == *"Finance Dashboard"* || "$body" == *"Sign in"* ]]
}

stop_listen_port() {
  local port="$1"
  local pid
  pid="$(listen_pid "$port" || true)"
  if [[ -n "$pid" ]]; then
    log "stopping stale process $pid on port $port"
    kill "$pid" 2>/dev/null || true
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" 2>/dev/null || true
    fi
  fi
}

stop_stale_stack() {
  local pid
  if pid_alive "$FRONTEND_PID_FILE"; then
    pid="$(cat "$FRONTEND_PID_FILE" 2>/dev/null || true)"
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  fi
  if pid_alive "$BACKEND_PID_FILE"; then
    pid="$(cat "$BACKEND_PID_FILE" 2>/dev/null || true)"
    [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
  fi
  stop_listen_port "$FRONTEND_PORT"
  stop_listen_port "$BACKEND_PORT"
  rm -f "$FRONTEND_PID_FILE" "$BACKEND_PID_FILE"
}

listen_pid() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$port" -sTCP:LISTEN -t 2>/dev/null | head -1
  elif command -v ss >/dev/null 2>&1; then
    ss -ltnp "sport = :$port" 2>/dev/null | sed -n 's/.*pid=\([0-9]*\).*/\1/p' | head -1
  else
    return 1
  fi
}

pid_alive() {
  local file="$1"
  [[ -f "$file" ]] || return 1
  local pid
  pid="$(cat "$file" 2>/dev/null || true)"
  [[ -n "$pid" ]] || return 1
  kill -0 "$pid" 2>/dev/null
}

foreign_port_message() {
  local port="$1"
  local pid
  pid="$(listen_pid "$port" || true)"
  if [[ -n "$pid" ]]; then
    printf 'Port %s is already in use (process %s), and it is not Rob'\''s Finance. Leave that app running and try again after it has closed, or set ROBS_FINANCE_FRONTEND_PORT / ROBS_FINANCE_BACKEND_PORT.' "$port" "$pid"
  else
    printf 'Port %s is in use by another application, not Rob'\''s Finance.' "$port"
  fi
}

PLIST_SRC="$ROOT/scripts/launchd/com.robssolar.backend.plist"
PLIST_DST="$HOME/Library/LaunchAgents/com.robssolar.backend.plist"
AGENT_LABEL="com.robssolar.backend"
AGENT_STAMP="$LOG_DIR/backend-agent.sha256"

_plist_sha256() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    wc -c <"$1"
  fi
}

_launchd_loaded() {
  local uid="$1"
  launchctl print "gui/$uid/$AGENT_LABEL" >/dev/null 2>&1 \
    || launchctl list "$AGENT_LABEL" >/dev/null 2>&1
}

install_backend_agent_plist() {
  if command -v write_backend_launch_agent >/dev/null 2>&1; then
    write_backend_launch_agent "$ROOT" "$PLIST_DST"
  elif [[ -f "$PLIST_SRC" ]]; then
    mkdir -p "$HOME/Library/LaunchAgents"
    cp "$PLIST_SRC" "$PLIST_DST" 2>/dev/null || true
  fi
}

# Replace a previously loaded KeepAlive=true job. Overwriting the plist file
# is not enough — launchd keeps the old definition until bootout.
reload_backend_agent_if_stale() {
  local uid="$1"
  local hash stamp
  [[ -f "$PLIST_DST" ]] || return 1
  hash="$(_plist_sha256 "$PLIST_DST")"
  stamp="$(cat "$AGENT_STAMP" 2>/dev/null || true)"
  if [[ "$stamp" == "$hash" ]] && _launchd_loaded "$uid"; then
    return 1
  fi
  launchctl bootout "gui/$uid/$AGENT_LABEL" 2>/dev/null \
    || launchctl unload "$PLIST_DST" 2>/dev/null || true
  launchctl bootstrap "gui/$uid" "$PLIST_DST" 2>/dev/null \
    || launchctl load "$PLIST_DST" 2>/dev/null || true
  printf '%s\n' "$hash" >"$AGENT_STAMP"
  log "loaded backend launchd agent (KeepAlive=false, no login start)"
  return 0
}

ensure_backend_agent() {
  # KeepAlive and RunAtLoad are both false. The API starts only when this
  # Dock launcher kickstarts the agent. Boolean KeepAlive=true would start
  # at every Mac login after the first click.
  if [[ "$(uname -s)" != "Darwin" ]]; then
    start_backend_process
    return
  fi
  local uid
  uid="$(id -u)"
  install_backend_agent_plist
  if [[ ! -f "$PLIST_DST" ]]; then
    log "backend plist missing ($PLIST_DST); starting backend process"
    start_backend_process
    return
  fi
  reload_backend_agent_if_stale "$uid" || true
  if ! backend_up; then
    launchctl kickstart "gui/$uid/$AGENT_LABEL" 2>/dev/null \
      || launchctl start "$AGENT_LABEL" 2>/dev/null \
      || start_backend_process
    log "kickstarted backend launchd agent"
  fi
}

start_backend_process() {
  if backend_up; then
    return 0
  fi
  local occupied
  occupied="$(listen_pid "$BACKEND_PORT" || true)"
  if [[ -n "$occupied" ]]; then
    log "port $BACKEND_PORT occupied by pid $occupied and health check failed"
    return 1
  fi
  if pid_alive "$BACKEND_PID_FILE"; then
    return 0
  fi
  cd "$ROOT" || return 1
  nohup bash "$ROOT/scripts/backend-service.sh" >>"$SERVER_LOG" 2>&1 &
  echo $! >"$BACKEND_PID_FILE"
  log "started backend pid $(cat "$BACKEND_PID_FILE")"
}

needs_build() {
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
    notify "Rob's Finance" "Building dashboard (one-time after update)…"
    log "frontend build is stale or missing — running production build"
    bash "$ROOT/scripts/build-frontend.sh" >>"$SERVER_LOG" 2>&1 || log "frontend build failed"
  else
    log "frontend build is fresh — skipping rebuild"
  fi
  cd "$ROOT/frontend" || exit 1
  local -a start_cmd
  start_cmd=( "$NPM" run start -- --port "$FRONTEND_PORT" --hostname "$HOST" )
  if [[ ! -f "$ROOT/frontend/.next/BUILD_ID" ]]; then
    log "no production build; falling back to next dev"
    start_cmd=( "$NPM" run dev -- --port "$FRONTEND_PORT" --hostname "$HOST" )
  fi
  if [[ "$(uname -m)" == "arm64" && -x /usr/bin/arch ]]; then
    nohup /usr/bin/arch -arm64 "${start_cmd[@]}" >>"$SERVER_LOG" 2>&1 &
  else
    nohup "${start_cmd[@]}" >>"$SERVER_LOG" 2>&1 &
  fi
  echo $! >"$FRONTEND_PID_FILE"
  log "started frontend pid $(cat "$FRONTEND_PID_FILE")"
}

start_stack() {
  notify "Rob's Finance" "Starting dashboard…"
  log "starting stack (backend + frontend)"
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

open_dashboard() {
  log "opening $URL"
  if [[ "${ROBS_FINANCE_SKIP_OPEN:-0}" == "1" ]]; then
    log "skipping browser open (ROBS_FINANCE_SKIP_OPEN=1)"
    return 0
  fi
  if [[ -n "$OPEN" && -x "$OPEN" ]]; then
    "$OPEN" "$URL" || true
  elif command -v xdg-open >/dev/null 2>&1 && [[ -n "${DISPLAY:-}" ]]; then
    xdg-open "$URL" >/dev/null 2>&1 || true
  else
    log "no browser opener; dashboard is at $URL"
  fi
  notify "Rob's Finance" "Dashboard opened"
}

log "launch started project=$ROOT port=$FRONTEND_PORT backend=$BACKEND_PORT npm=${NPM:-missing}"

if [[ ! -d "$ROOT/backend" || ! -d "$ROOT/frontend" ]]; then
  log "project path missing backend/frontend: $ROOT"
  alert "Rob's Finance could not start" "Could not find the Rob's Finance project. Expected backend and frontend under $ROOT."
  exit 1
fi

if [[ -d "$ROOT/frontend/src/app/(energy)" ]]; then
  log "refusing Energy checkout at $ROOT"
  if command -v resolve_robs_solar_root >/dev/null 2>&1; then
    ROOT="$(resolve_robs_solar_root || true)"
    export ROBS_SOLAR_ROOT="$ROOT"
    log "switched project root to $ROOT"
  fi
fi
if [[ -z "$ROOT" || -d "$ROOT/frontend/src/app/(energy)" || ! -d "$ROOT/backend" ]]; then
  alert "Rob's Finance could not start" "This copy still has Energy pages. Open the All repo, run git pull, then click Rob's Finance again."
  exit 1
fi

if is_up && looks_like_energy_build; then
  log "localhost is serving a leftover Energy build — stopping it"
  stop_stale_stack
  sleep 1
  if is_up && looks_like_energy_build; then
    log "leftover Energy build still present after stop"
    alert "Rob's Finance could not start" "Port $FRONTEND_PORT is still serving an old Energy build. Close that process, then click Rob's Finance again. Check $LOG for details."
    exit 1
  fi
fi

if is_up && backend_up && looks_like_robs_finance && ! looks_like_energy_build; then
  log "dashboard and backend already running — reusing instance"
  # Still replace a leftover KeepAlive=true LaunchAgent from older installs.
  ensure_backend_agent
  if backend_up; then
    open_dashboard
    exit 0
  fi
fi

if is_up && (! looks_like_robs_finance || looks_like_energy_build); then
  msg="$(foreign_port_message "$FRONTEND_PORT")"
  log "$msg"
  alert "Rob's Finance could not start" "$msg Check $LOG for details."
  exit 1
fi

if [[ -z "$NPM" ]]; then
  log "npm not found"
  alert "Rob's Finance could not start" "Node.js npm was not found. Install Node from https://nodejs.org then click Rob's Finance again."
  exit 1
fi

if ! backend_up; then
  occupied="$(listen_pid "$BACKEND_PORT" || true)"
  if [[ -n "$occupied" ]]; then
    msg="$(foreign_port_message "$BACKEND_PORT")"
    log "$msg"
    alert "Rob's Finance could not start" "$msg Check $LOG for details."
    exit 1
  fi
fi

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

if is_up && backend_up; then
  if looks_like_energy_build; then
    log "refusing to open leftover Energy build after launch"
    alert "Rob's Finance could not start" "Port $FRONTEND_PORT is still serving an old Energy build. Close that process, then click Rob's Finance again. Check $LOG for details."
    exit 1
  fi
  log "readiness ok frontend=$URL backend=$HEALTH_URL"
  open_dashboard
  exit 0
fi

log "dashboard did not become reachable"
alert "Rob's Finance did not start in time" "Check $LOG for details."
exit 1
