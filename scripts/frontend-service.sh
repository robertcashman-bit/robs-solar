#!/usr/bin/env bash
# Frontend entrypoint for the launchd LaunchAgent (com.robssolar.frontend).
# Serves the pre-built Next.js production bundle on :3000. Kept alive by launchd
# (KeepAlive) so the dashboard survives sleep, crashes, and the Dock launcher
# process exiting — the same supervision the backend already gets.
#
# Rationale: the old launcher started the frontend with `nohup npm run start &`,
# which had no supervisor. When its parent process group was torn down (or the
# Mac slept, or Next crashed) the server vanished. The cached PWA shell still
# loaded but every /backend/* API call failed with "Failed to fetch".
set -uo pipefail

ROOT="${ROBS_SOLAR_ROOT:-/Users/robertcashman/robs-solar}"
cd "$ROOT/frontend" || exit 1

# Ensure the native CSS binaries resolve for the running arch. Non-fatal: a
# missing build below is the real gate.
bash "$ROOT/scripts/ensure-lightningcss.sh" >/dev/null 2>&1 || true

# Serve a production build. Only build here as a fallback when none exists — the
# Dock launcher (mac-launch.sh) is responsible for rebuilding on code changes
# and then restarting this agent.
if [[ ! -f "$ROOT/frontend/.next/BUILD_ID" ]]; then
  bash "$ROOT/scripts/build-frontend.sh"
fi

# Pin to native arch so the universal Node loads arm64 native modules
# (lightningcss / tailwind oxide) instead of defaulting to x86_64 under Rosetta.
if [[ "$(uname -m)" == "arm64" && -x /usr/bin/arch ]]; then
  exec /usr/bin/arch -arm64 npm run start -- --port 3000
fi
exec npm run start -- --port 3000
