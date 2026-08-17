#!/usr/bin/env bash
# Frontend entrypoint for the launchd LaunchAgent (com.robssolar.frontend).
set -uo pipefail

_THIS="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$_THIS/mac-root.sh" ]]; then
  # shellcheck source=mac-root.sh
  source "$_THIS/mac-root.sh"
fi

if [[ -d "$_THIS/../frontend" ]]; then
  ROOT="$(cd "$_THIS/.." && pwd)"
elif command -v resolve_robs_solar_root >/dev/null 2>&1; then
  ROOT="$(resolve_robs_solar_root || true)"
fi
ROOT="${ROOT:-${ROBS_SOLAR_ROOT:-$HOME/robs-solar}}"
cd "$ROOT/frontend" || exit 1

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
export NODE_ENV=production
PORT="${ROBS_FINANCE_FRONTEND_PORT:-3000}"

if [[ "$(uname -m)" == "arm64" && -x /usr/bin/arch ]]; then
  exec /usr/bin/arch -arm64 npm run start -- --port "$PORT" --hostname 127.0.0.1
fi
exec npm run start -- --port "$PORT" --hostname 127.0.0.1
