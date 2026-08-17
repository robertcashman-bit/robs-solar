#!/bin/bash
# Double-click on the Mac Desktop: start Rob's Finance.
# Copied to Desktop/Downloads, so this file stays self-contained.
set -uo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

home="${HOME:-/Users/robertcashman}"

looks_like_app() {
  [[ -x "$1/Contents/MacOS/RobsFinance" ]]
}

looks_like_solar() {
  [[ -x "$1/scripts/mac-launch.sh" && -d "$1/backend" && -d "$1/frontend" ]] || return 1
  [[ ! -d "$1/frontend/src/app/(energy)" ]]
}

for app in \
  "/Applications/RobsFinance.app" \
  "$home/Applications/RobsFinance.app"
do
  if looks_like_app "$app"; then
    if command -v open >/dev/null 2>&1; then
      exec open "$app"
    fi
    exec /bin/bash "$app/Contents/MacOS/RobsFinance"
  fi
done

if [[ -n "${ROBS_SOLAR_ROOT:-}" ]] && looks_like_solar "${ROBS_SOLAR_ROOT}"; then
  export ROBS_SOLAR_ROOT
  exec /bin/bash "${ROBS_SOLAR_ROOT}/scripts/mac-launch.sh"
fi

for candidate in \
  "$home/All/robs-solar" \
  "$home/src/All/robs-solar" \
  "$home/Developer/All/robs-solar" \
  "$home/Documents/All/robs-solar" \
  "$home/code/All/robs-solar" \
  "$home/Projects/All/robs-solar" \
  "$home/repos/All/robs-solar" \
  "$home/GitHub/All/robs-solar" \
  "$home/robertdavidcashman-droid/All/robs-solar" \
  "$home/workspace/robs-solar" \
  "$home/robs-solar"
do
  if looks_like_solar "$candidate"; then
    export ROBS_SOLAR_ROOT="$candidate"
    exec /bin/bash "$candidate/scripts/mac-launch.sh"
  fi
done

# Local app is not installed. Open the live Finance site instead of bouncing.
if command -v open >/dev/null 2>&1; then
  exec open "https://robs-solar.vercel.app/login?send=1"
fi
if command -v osascript >/dev/null 2>&1; then
  /usr/bin/osascript -e 'display alert "Rob'\''s Finance could not start" message "The app was not found. Open https://robs-solar.vercel.app or run the Mac installer from that site."' 2>/dev/null || true
fi
exit 1
