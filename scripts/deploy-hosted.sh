#!/usr/bin/env bash
# Hosted deployment helper: commit is assumed done; this deploys frontend to Vercel
# and prints the Render blueprint link for the backend (one-time GitHub connect).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Deploying frontend to Vercel (production)…"
cd frontend
if [[ -z "${BACKEND_URL:-}" ]]; then
  echo "WARNING: BACKEND_URL is not set. Set it to your Render API URL, e.g."
  echo "  export BACKEND_URL=https://robs-solar-api.onrender.com"
  echo "Continuing — you can set BACKEND_URL in the Vercel dashboard after Render is up."
fi

if command -v vercel >/dev/null 2>&1; then
  VC=vercel
else
  VC="npx --yes vercel"
fi

$VC deploy --prod --yes \
  ${BACKEND_URL:+--env "BACKEND_URL=$BACKEND_URL"} \
  ${VERCEL_TOKEN:+--token "$VERCEL_TOKEN"}

echo ""
echo "==> Backend (Render)"
echo "1. Open https://dashboard.render.com/blueprint/new?repo=https://github.com/robertcashman-bit/robs-solar"
echo "2. Apply the blueprint (creates robs-solar-api with persistent disk)."
echo "3. Copy the service URL, then set BACKEND_URL in Vercel:"
echo "   vercel env add BACKEND_URL production   # paste https://robs-solar-api.onrender.com"
echo "4. Sync secrets from your local .env:"
echo "   export RENDER_API_KEY=... RENDER_SERVICE_ID=srv-..."
echo "   bash scripts/push-render-secrets.sh"
echo "5. Redeploy Vercel: cd frontend && vercel --prod"
