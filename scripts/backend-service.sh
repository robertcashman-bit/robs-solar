#!/usr/bin/env bash
# Backend entrypoint for the launchd LaunchAgent (com.robssolar.backend).
# Kept tiny and self-contained so launchd can KeepAlive it independently of the
# Dock launcher or any interactive shell.
set -uo pipefail

ROOT="${ROBS_SOLAR_ROOT:-/Users/robertcashman/robs-solar}"
cd "$ROOT/backend" || exit 1

# shellcheck disable=SC1091
source .venv/bin/activate

# Pin to native arch so the universal Python loads arm64 wheels (pydantic_core,
# etc.). launchd can otherwise default the process to x86_64 under Rosetta.
if [[ "$(uname -m)" == "arm64" && -x /usr/bin/arch ]]; then
  exec /usr/bin/arch -arm64 uvicorn app.main:app --host 127.0.0.1 --port 8000
fi
exec uvicorn app.main:app --host 127.0.0.1 --port 8000
