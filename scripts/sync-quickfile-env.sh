#!/usr/bin/env bash
# Append QuickFile credentials from Custody Note settings into backend/.env.
# Custody Note stores keys in its encrypted DB — copy values from Settings → QuickFile
# or pass them as env vars when running this script.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${ROOT}/backend/.env"

ACCOUNT="${QUICKFILE_ACCOUNT_NUMBER:-${1:-}}"
API_KEY="${QUICKFILE_API_KEY:-${2:-}}"
APP_ID="${QUICKFILE_APPLICATION_ID:-${3:-}}"

if [[ -z "$ACCOUNT" || -z "$API_KEY" || -z "$APP_ID" ]]; then
  cat <<'EOF'
Usage:
  QUICKFILE_ACCOUNT_NUMBER=... QUICKFILE_API_KEY=... QUICKFILE_APPLICATION_ID=... \
    bash scripts/sync-quickfile-env.sh

  bash scripts/sync-quickfile-env.sh <account_number> <api_key> <application_id>

Copy the three values from Custody Note → Settings → QuickFile (same as Rob's Finance).
EOF
  exit 1
fi

touch "$ENV_FILE"
upsert() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    if [[ "$(uname)" == "Darwin" ]]; then
      sed -i '' "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    else
      sed -i "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
    fi
  else
    printf '%s=%s\n' "$key" "$value" >>"$ENV_FILE"
  fi
}

upsert QUICKFILE_ACCOUNT_NUMBER "$ACCOUNT"
upsert QUICKFILE_API_KEY "$API_KEY"
upsert QUICKFILE_APPLICATION_ID "$APP_ID"

echo "Updated QuickFile keys in backend/.env"
echo "Run: bash scripts/push-render-secrets.sh  (to sync to Render)"
