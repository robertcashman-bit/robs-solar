#!/usr/bin/env bash
# Push backend/.env vars to the linked Vercel project (production).
# Values are read locally and sent to Vercel; nothing is printed.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${1:-$ROOT/backend/.env}"
cd "$ROOT"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

if command -v vercel >/dev/null 2>&1; then
  VC=vercel
else
  VC="npx --yes vercel"
fi

# Do not overwrite hosted DATABASE_URL. Local .env is file-backed SQLite; Vercel
# already has Neon ROBS_FINANCE_* URLs and the API prefers those over /tmp SQLite.
$VC env add APP_ENV production --force <<< "production" >/dev/null 2>&1 || true

while IFS= read -r line || [[ -n "$line" ]]; do
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  [[ -z "${line// }" ]] && continue
  key="${line%%=*}"
  key="${key//[[:space:]]/}"
  val="${line#*=}"
  val="${val%\"}"
  val="${val#\"}"
  [[ -z "$key" || -z "$val" ]] && continue
  [[ "$key" == "DATABASE_URL" ]] && continue
  printf '%s' "$val" | $VC env add "$key" production --force --sensitive >/dev/null 2>&1 || true
done < "$ENV_FILE"

echo "Vercel production env synced from $ENV_FILE (values not shown)."
