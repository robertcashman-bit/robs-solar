#!/usr/bin/env bash
# Wire personal-finance integrations that can be copied from this Mac.
# Energy / Tesla / Octopus are intentionally skipped.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ALL_ROOT="$(cd "$ROOT/.." && pwd)"

export CUSTODY_NOTE_WEBSITE="${CUSTODY_NOTE_WEBSITE:-$ALL_ROOT/custody-note-website}"
export CUSTODY_NOTE_APP="${CUSTODY_NOTE_APP:-$ALL_ROOT/custody-note-app}"
if [[ ! -d "$CUSTODY_NOTE_WEBSITE" ]]; then
  export CUSTODY_NOTE_WEBSITE="${HOME}/custody-note-website"
fi
if [[ ! -d "$CUSTODY_NOTE_APP" ]]; then
  export CUSTODY_NOTE_APP="${HOME}/custody-note-app"
fi

find_qf_sync() {
  local candidate
  for candidate in \
    "$CUSTODY_NOTE_APP/lib/quickfileSettingsSync.js" \
    "$CUSTODY_NOTE_APP/custody-note-app-source/lib/quickfileSettingsSync.js" \
    "$HOME/custody-note-app/lib/quickfileSettingsSync.js" \
    "$HOME/custody-note-app/custody-note-app-source/lib/quickfileSettingsSync.js" \
    "/tmp/custody-note-app/custody-note-app-source/lib/quickfileSettingsSync.js" \
    "/tmp/other-git/custody-note-app/lib/quickfileSettingsSync.js"
  do
    if [[ -f "$candidate" ]]; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

echo "==> Personal finance connection (no Energy)"
echo "    Finance app: $ROOT"
echo "    Custody Note website: $CUSTODY_NOTE_WEBSITE"
echo "    Custody Note app: $CUSTODY_NOTE_APP"
echo ""

QF_SYNC="$(find_qf_sync || true)"
if [[ -n "$QF_SYNC" ]] && {
  [[ -f "$CUSTODY_NOTE_WEBSITE/.env.local" ]] \
    || [[ -n "${KV_REST_API_URL:-}" && -n "${KV_REST_API_TOKEN:-}" ]] \
    || [[ -n "${VERCEL_TOKEN:-}" ]]
}; then
  echo "==> Trying QuickFile import from Custody Note cloud..."
  if [[ "$QF_SYNC" == *"/custody-note-app-source/"* ]]; then
    export CUSTODY_NOTE_APP="$(dirname "$(dirname "$QF_SYNC")")"
  else
    export CUSTODY_NOTE_APP="$(dirname "$(dirname "$QF_SYNC")")"
  fi
  if bash "$SCRIPT_DIR/wire-quickfile-auto.sh"; then
    echo "QuickFile copied into backend/.env and the API (if it was reachable)."
  else
    echo "QuickFile import failed. Paste Account number / API key / Application ID in Settings."
  fi
else
  echo "QuickFile is not on this machine's Custody Note checkout."
  echo "On the Mac that already has Custody Note QuickFile:"
  echo "  1. Open Custody Note → Settings → QuickFile"
  echo "  2. Copy the three fields into Rob's Finance → Settings"
  echo "  or run this script there after pulling All."
fi

echo ""
echo "==> Still needs you (cannot be invented from this repo)"
echo "  Lunch Flow: Destinations → API key → Settings → Lunch Flow → Save / Test / Sync"
echo "  TrueLayer: paste Client ID / secret / redirect URI in Settings → Open Banking"
echo "  Funding Circle: enter the outstanding loan in Settings, or pull it after TrueLayer sync"
echo "  Manual accounts already work without any of those."
echo ""
echo "Restart the Finance backend after pasting keys, then click Test / Sync in Settings."
