#!/usr/bin/env bash
# Repair and deploy hosted Rob's Finance automatically.
#
# Default (no Render): Vercel multi-service — frontend + FastAPI on one project
# via robs-solar/vercel.json. Removes broken BACKEND_URL (localhost proxy).
#
# Optional Render path: DEPLOY_MODE=render-external BACKEND_URL=https://... VERCEL_TOKEN=...
#
# Usage:
#   VERCEL_TOKEN=xxx bash scripts/repair-hosted.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SCOPE="${VERCEL_SCOPE:-robert-cashmans-projects}"
TEAM="${VERCEL_TEAM_ID:-team_wbvkpoLfvbg9qFwg5LqJLAjN}"
PROJECT_ID="${VERCEL_PROJECT_ID:-prj_VTwGcysJvmjZe3rxZIsAh3Kwuy3w}"
DEPLOY_MODE="${DEPLOY_MODE:-vercel-multi}"
BACKEND_URL="${BACKEND_URL:-https://robs-solar-api.onrender.com}"

if command -v vercel >/dev/null 2>&1; then
  VC=vercel
else
  VC="npx --yes vercel@54.20.1"
fi

api() {
  local method="$1" path="$2" body="${3:-}"
  local url="https://api.vercel.com${path}"
  [[ "$path" != *"?"* ]] && url="${url}?teamId=${TEAM}" || url="${url}&teamId=${TEAM}"
  if [[ -n "$body" ]]; then
    curl -fsS -X "$method" "$url" \
      -H "Authorization: Bearer ${VERCEL_TOKEN}" \
      -H "Content-Type: application/json" \
      -d "$body"
  else
    curl -fsS -X "$method" "$url" \
      -H "Authorization: Bearer ${VERCEL_TOKEN}"
  fi
}

require_token() {
  if [[ -z "${VERCEL_TOKEN:-}" ]]; then
    echo "ERROR: VERCEL_TOKEN is required." >&2
    echo "Add it as a Cloud Agent secret or GitHub Actions secret, then re-run." >&2
    exit 1
  fi
}

remove_backend_url() {
  echo "==> Removing BACKEND_URL from Vercel (breaks multi-service / localhost proxy)"
  local envs
  envs="$(api GET "/v9/projects/${PROJECT_ID}/env" || echo '{"envs":[]}')"
  while IFS= read -r env_id; do
    [[ -z "$env_id" ]] && continue
    api DELETE "/v9/projects/${PROJECT_ID}/env/${env_id}" >/dev/null || true
    echo "    deleted env id ${env_id}"
  done < <(ENV_JSON="$envs" python3 - <<'PY'
import json, os
data = json.loads(os.environ["ENV_JSON"])
for item in data.get("envs", []):
    if item.get("key") == "BACKEND_URL":
        print(item["id"])
PY
)
}

set_env() {
  local key="$1" value="$2" sensitive="${3:-false}"
  local type="plain"
  [[ "$sensitive" == "true" ]] && type="encrypted"
  api POST "/v10/projects/${PROJECT_ID}/env?upsert=true" \
    "{\"key\":\"${key}\",\"value\":\"${value}\",\"type\":\"${type}\",\"target\":[\"production\",\"preview\",\"development\"]}" \
    >/dev/null 2>&1 || true
}

project_has_env() {
  local key="$1"
  local envs
  # Fail closed: a failed GET must not look like "key absent" or we may
  # overwrite DATABASE_URL / SECRET_KEY via set_env upsert.
  if ! envs="$(api GET "/v9/projects/${PROJECT_ID}/env")"; then
    echo "ERROR: failed to list Vercel env vars; cannot safely check for ${key}." >&2
    exit 1
  fi
  ENV_JSON="$envs" LOOKUP_KEY="$key" python3 - <<'PY'
import json, os, sys
data = json.loads(os.environ["ENV_JSON"])
key = os.environ["LOOKUP_KEY"]
sys.exit(0 if any(item.get("key") == key for item in data.get("envs", [])) else 1)
PY
}

ensure_min_api_env() {
  echo "==> Ensuring minimum API env on Vercel"
  set_env APP_ENV production
  # Do not overwrite a persistent DATABASE_URL if one is already configured.
  if [[ -n "${DATABASE_URL:-}" ]]; then
    set_env DATABASE_URL "$DATABASE_URL"
  elif project_has_env DATABASE_URL; then
    echo "    keeping existing DATABASE_URL"
  else
    set_env DATABASE_URL "sqlite+aiosqlite:////tmp/robs_solar.db"
  fi
  set_env ADAPTER_MODE "${ADAPTER_MODE:-simulator}"
  set_env READ_ONLY "${READ_ONLY:-true}"
  set_env ENABLE_LIVE_WRITES "${ENABLE_LIVE_WRITES:-false}"
  set_env CORS_ORIGINS "https://robs-solar.vercel.app,http://127.0.0.1:3000,http://localhost:3000"
  set_env ADMIN_USERNAME "${ADMIN_USERNAME:-admin}"
  set_env ADMIN_EMAIL "${ADMIN_EMAIL:-robertdavidcashman@gmail.com}"
  set_env PUBLIC_APP_URL "https://robs-solar.vercel.app"
  set_env MAGIC_CODE_ENABLED true
  set_env MAGIC_CODE_ADMIN_EMAILS "${ADMIN_EMAIL:-robertdavidcashman@gmail.com}"
  if [[ -n "${RESEND_API_KEY:-}" ]]; then
    set_env RESEND_API_KEY "$RESEND_API_KEY" true
  elif project_has_env RESEND_API_KEY; then
    echo "    keeping existing RESEND_API_KEY"
  fi
  # Never rotate SECRET_KEY on a routine deploy — that invalidates every login.
  if [[ -n "${SECRET_KEY:-}" ]]; then
    set_env SECRET_KEY "$SECRET_KEY" true
  elif project_has_env SECRET_KEY; then
    echo "    keeping existing SECRET_KEY"
  else
    SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
    set_env SECRET_KEY "$SECRET_KEY" true
  fi
}

restore_monorepo_root() {
  echo "==> Restoring Vercel root directory to robs-solar"
  api PATCH "/v9/projects/${PROJECT_ID}" '{"rootDirectory":"robs-solar","framework":null}' >/dev/null || true
}

deploy_vercel_multi() {
  require_token
  remove_backend_url
  # CLI upload treats --cwd as the project root. If Vercel also has
  # rootDirectory=robs-solar, it looks for robs-solar/robs-solar and fails.
  echo "==> Clearing Vercel root for CLI upload from robs-solar/"
  api PATCH "/v9/projects/${PROJECT_ID}" '{"rootDirectory":null,"framework":null}' >/dev/null
  trap restore_monorepo_root EXIT
  ensure_min_api_env
  echo "==> Building frontend"
  npm ci --prefer-offline
  npm run build
  echo "==> Deploying production (frontend + API via vercel.json)"
  export VERCEL_ORG_ID="${TEAM}"
  export VERCEL_PROJECT_ID="${PROJECT_ID}"
  $VC deploy --prod --yes --token="${VERCEL_TOKEN}" --cwd "${ROOT}"
  echo ""
  echo "Done. Verify:"
  echo "  curl -sI https://robs-solar.vercel.app/backend/health"
  echo "  curl -sI https://robs-solar.vercel.app/"
}

deploy_render_external() {
  require_token
  echo "==> Checking Render API at ${BACKEND_URL}/health"
  if ! curl -fsS --max-time 20 "${BACKEND_URL}/health" >/dev/null 2>&1; then
    echo "ERROR: Render API not reachable at ${BACKEND_URL}" >&2
    echo "Use DEPLOY_MODE=vercel-multi (default) or deploy Render first." >&2
    exit 1
  fi
  echo "==> Setting BACKEND_URL=${BACKEND_URL} on Vercel"
  set_env BACKEND_URL "$BACKEND_URL"
  api PATCH "/v9/projects/${PROJECT_ID}" '{"rootDirectory":"robs-solar","framework":"nextjs"}' >/dev/null
  echo "==> Building and deploying frontend only"
  npm ci --prefer-offline
  npm run build
  $VC deploy --prod --yes --token="${VERCEL_TOKEN}" --scope="${SCOPE}" --cwd "${ROOT}/frontend"
  api PATCH "/v9/projects/${PROJECT_ID}" '{"rootDirectory":"robs-solar"}' >/dev/null
}

case "$DEPLOY_MODE" in
  vercel-multi) deploy_vercel_multi ;;
  render-external) deploy_render_external ;;
  *)
    echo "Unknown DEPLOY_MODE: $DEPLOY_MODE (use vercel-multi or render-external)" >&2
    exit 1
    ;;
esac
