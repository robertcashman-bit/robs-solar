#!/usr/bin/env bash
# Build the Next.js frontend for production so the Dock launcher can serve a
# pre-compiled bundle (next start) instead of compiling on demand (next dev).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

bash "$ROOT/scripts/ensure-lightningcss.sh"

cd "$ROOT/frontend"
if [[ "$(uname -m)" == "arm64" && -x /usr/bin/arch ]]; then
  /usr/bin/arch -arm64 npm run build
else
  npm run build
fi

echo "Frontend production build ready (.next)"
