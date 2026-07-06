#!/usr/bin/env bash
# Push secret env vars from backend/.env to a Render web service.
# Requires RENDER_API_KEY (from https://dashboard.render.com/u/settings#api-keys)
# and RENDER_SERVICE_ID (the robs-solar-api service id after blueprint deploy).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${1:-$ROOT/backend/.env}"
SERVICE_ID="${RENDER_SERVICE_ID:?Set RENDER_SERVICE_ID to your Render web service id}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

KEYS=(
  ADMIN_USERNAME ADMIN_PASSWORD VIEWER_USERNAME VIEWER_PASSWORD
  SECRET_KEY SUNSYNK_USERNAME SUNSYNK_PASSWORD SUNSYNK_PLANT_ID SUNSYNK_INVERTER_SN
  SUNSYNK_ENABLE_UNVERIFIED_WRITES
  OCTOPUS_API_KEY OCTOPUS_ACCOUNT_NUMBER OCTOPUS_MPAN OCTOPUS_METER_SERIAL OCTOPUS_REGION
  OPENAI_API_KEY AI_ENABLED AI_MODEL
  QUICKFILE_ACCOUNT_NUMBER QUICKFILE_API_KEY QUICKFILE_APPLICATION_ID
  READ_ONLY ENABLE_LIVE_WRITES ADAPTER_MODE
  TARIFF_TIMEZONE PEAK_IMPORT_GUARD_ENABLED AUTO_SCHEDULE_ENABLED
  OPEN_BANKING_PROVIDER ENABLE_BANKING_APPLICATION_ID ENABLE_BANKING_PRIVATE_KEY_PEM
  ENABLE_BANKING_ENVIRONMENT OPEN_BANKING_REDIRECT_URL
)

payload='{"envVars":['
first=true
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  [[ -z "${line// }" ]] && continue
  key="${line%%=*}"
  key="${key//[[:space:]]/}"
  val="${line#*=}"
  val="${val%\"}"
  val="${val#\"}"
  for allowed in "${KEYS[@]}"; do
    if [[ "$key" == "$allowed" && -n "$val" ]]; then
      if [[ "$first" == true ]]; then first=false; else payload+=','; fi
      esc="${val//\\/\\\\}"
      esc="${esc//\"/\\\"}"
      payload+="{\"key\":\"$key\",\"value\":\"$esc\"}"
      break
    fi
  done
done < "$ENV_FILE"
payload+=']}'

echo "Updating Render service $SERVICE_ID env vars (values not printed)…"
curl -fsS -X PUT \
  -H "Authorization: Bearer $RENDER_API_KEY" \
  -H "Content-Type: application/json" \
  "https://api.render.com/v1/services/$SERVICE_ID/env-vars" \
  -d "$payload" >/dev/null

echo "Done. Trigger a manual deploy in Render if the service was already live."
