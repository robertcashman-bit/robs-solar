#!/usr/bin/env bash
# Thin Dock wrapper. Always exec the latest launcher from the checkout
# so a git pull updates Rob's Finance without rebuilding the .app.
set -uo pipefail

export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

_THIS="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$_THIS/mac-root.sh" ]]; then
  # shellcheck source=mac-root.sh
  source "$_THIS/mac-root.sh"
fi

ROOT=""
BAKED=""
if [[ -n "${ROBS_FINANCE_APP_BUNDLE:-}" ]]; then
  BAKED="${ROBS_FINANCE_APP_BUNDLE}/Contents/Resources/project-root"
fi
if [[ -z "$ROOT" && -n "$BAKED" ]] && command -v read_baked_project_root >/dev/null 2>&1; then
  ROOT="$(read_baked_project_root "$BAKED" || true)"
fi
if [[ -d "$_THIS/../backend" && -x "$_THIS/mac-launch.sh" ]]; then
  ROOT="$(cd "$_THIS/.." && pwd)"
elif command -v resolve_robs_solar_root >/dev/null 2>&1; then
  ROOT="$(resolve_robs_solar_root || true)"
fi
ROOT="${ROOT:-${ROBS_SOLAR_ROOT:-$HOME/All/robs-solar}}"

if [[ ! -x "$ROOT/scripts/mac-launch.sh" ]]; then
  if command -v open_hosted_robs_finance >/dev/null 2>&1 && open_hosted_robs_finance; then
    exit 0
  fi
  if command -v open >/dev/null 2>&1; then
    open "https://robs-solar.vercel.app/login"
    exit 0
  fi
  if [[ -x /usr/bin/osascript ]]; then
    /usr/bin/osascript -e 'display alert "Rob'\''s Finance could not start" message "The project folder was not found. Open https://robs-solar.vercel.app or install from that site."' 2>/dev/null || true
  fi
  exit 1
fi

export ROBS_SOLAR_ROOT="$ROOT"
exec /bin/bash "$ROOT/scripts/mac-launch.sh"
