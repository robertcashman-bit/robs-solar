#!/usr/bin/env bash
# Hosted deployment helper: commit is assumed done; this deploys frontend to Vercel
# and prints the Render blueprint link for the backend (one-time GitHub connect).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Vercel project must use repo root (null), not a nested "robs-solar" folder — otherwise
# git pushes fail with NOW_SANDBOX_WORKER_ROOTDIR_NOT_EXIST and vercel.json services are ignored.
if [[ -n "${VERCEL_TOKEN:-}" ]]; then
  VERCEL_META="$(python3 <<'PY'
import json
from pathlib import Path
root = Path(".vercel")
if (root / "project.json").exists():
    data = json.loads((root / "project.json").read_text())
    print(data["projectId"], data["orgId"])
elif (root / "repo.json").exists():
    repo = json.loads((root / "repo.json").read_text())
    for p in repo.get("projects", []):
        if p.get("directory") in (".", ""):
            print(p["id"], p["orgId"])
            break
PY
)"
  if [[ -n "$VERCEL_META" ]]; then
    read -r PROJECT_ID ORG_ID <<< "$VERCEL_META"
    ROOT_DIR="$(curl -fsS -H "Authorization: Bearer $VERCEL_TOKEN" \
      "https://api.vercel.com/v9/projects/${PROJECT_ID}?teamId=${ORG_ID}" \
      | python3 -c "import json,sys; print(json.load(sys.stdin).get('rootDirectory') or '')")"
    if [[ -n "$ROOT_DIR" ]]; then
      echo "==> Fixing Vercel Root Directory (was '$ROOT_DIR', must be repo root)…"
      curl -fsS -X PATCH -H "Authorization: Bearer $VERCEL_TOKEN" -H "Content-Type: application/json" \
        -d '{"rootDirectory": null}' \
        "https://api.vercel.com/v9/projects/${PROJECT_ID}?teamId=${ORG_ID}" >/dev/null
    fi
  fi
fi

echo "==> Deploying frontend to Vercel (production)…"
cd "$ROOT"
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
echo "Tip: link the project once from repo root with: vercel link"

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
