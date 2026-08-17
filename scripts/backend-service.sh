#!/usr/bin/env bash
# Backend entrypoint for the launchd LaunchAgent (com.robssolar.backend)
# and for Linux/cloud launches. The Dock app kickstarts this; it does not
# start at login (KeepAlive and RunAtLoad are false).
set -uo pipefail

_THIS="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$_THIS/mac-root.sh" ]]; then
  # shellcheck source=mac-root.sh
  source "$_THIS/mac-root.sh"
fi

if [[ -d "$_THIS/../backend" ]]; then
  ROOT="$(cd "$_THIS/.." && pwd)"
elif command -v resolve_robs_solar_root >/dev/null 2>&1; then
  ROOT="$(resolve_robs_solar_root || true)"
fi
ROOT="${ROOT:-${ROBS_SOLAR_ROOT:-$HOME/robs-solar}}"
cd "$ROOT/backend" || exit 1

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

# shellcheck disable=SC1091
if [[ -f .venv/bin/activate ]]; then
  source .venv/bin/activate
fi

# Pin to native arch so the universal Python loads arm64 wheels (pydantic_core,
# etc.). launchd can otherwise default the process to x86_64 under Rosetta.
if [[ "$(uname -m)" == "arm64" && -x /usr/bin/arch ]]; then
  exec /usr/bin/arch -arm64 uvicorn app.main:app --host 127.0.0.1 --port "${ROBS_FINANCE_BACKEND_PORT:-8000}"
fi
exec uvicorn app.main:app --host 127.0.0.1 --port "${ROBS_FINANCE_BACKEND_PORT:-8000}"
