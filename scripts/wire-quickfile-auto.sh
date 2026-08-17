#!/usr/bin/env bash
# Pull QuickFile credentials from Custody Note cloud KV and wire into Rob's Finance automatically.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/backend/.env"

echo "==> Fetching QuickFile credentials from Custody Note cloud..."
JSON="$(node "$ROOT/scripts/fetch-quickfile-from-custody-cloud.mjs")"

ACCOUNT="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["account_number"])' "$JSON")"
API_KEY="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["api_key"])' "$JSON")"
APP_ID="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["application_id"])' "$JSON")"

echo "==> Writing backend/.env"
QUICKFILE_ACCOUNT_NUMBER="$ACCOUNT" \
QUICKFILE_API_KEY="$API_KEY" \
QUICKFILE_APPLICATION_ID="$APP_ID" \
  bash "$ROOT/scripts/sync-quickfile-env.sh"

if [[ -n "${RENDER_API_KEY:-}" && -n "${RENDER_SERVICE_ID:-}" ]]; then
  echo "==> Pushing secrets to Render..."
  bash "$ROOT/scripts/push-render-secrets.sh" "$ENV_FILE"
else
  echo "Skipping Render push (set RENDER_API_KEY and RENDER_SERVICE_ID to enable)."
fi

BACKEND_URL="${BACKEND_URL:-$(grep -E '^BACKEND_URL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)}"
BACKEND_URL="${BACKEND_URL:-https://robs-solar.vercel.app/backend}"
if [[ -n "$BACKEND_URL" ]]; then
  echo "==> Saving QuickFile settings to backend API at ${BACKEND_URL}..."
  ADMIN_USERNAME="${ADMIN_USERNAME:-$(grep -E '^ADMIN_USERNAME=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)}"
  ADMIN_PASSWORD="${ADMIN_PASSWORD:-$(grep -E '^ADMIN_PASSWORD=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)}"
  if [[ -z "$ADMIN_USERNAME" || -z "$ADMIN_PASSWORD" ]]; then
    echo "Skipping API save (ADMIN_USERNAME/ADMIN_PASSWORD not in env)."
  else
    COOKIE_JAR="$(mktemp)"
    CSRF="$(
      curl -fsS -c "$COOKIE_JAR" -X POST "$BACKEND_URL/auth/login" \
        -H "Content-Type: application/json" \
        -d "{\"username\":\"$ADMIN_USERNAME\",\"password\":\"$ADMIN_PASSWORD\"}" \
      | python3 -c 'import json,sys; print(json.load(sys.stdin).get("csrf_token",""))'
    )"
    curl -fsS -b "$COOKIE_JAR" -X PUT "$BACKEND_URL/finance/integrations/quickfile/settings" \
      -H "Content-Type: application/json" \
      -H "X-CSRF-Token: $CSRF" \
      -d "{\"account_number\":\"$ACCOUNT\",\"api_key\":\"$API_KEY\",\"application_id\":\"$APP_ID\"}" \
      >/dev/null
    echo "Backend QuickFile settings saved."
    rm -f "$COOKIE_JAR"
  fi
fi

echo "Done. QuickFile is wired locally$( [[ -n "${RENDER_API_KEY:-}" ]] && echo " and on Render" )."
