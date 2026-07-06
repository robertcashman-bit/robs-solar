#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
ADMIN_USER="${ADMIN_USER:-admin}"
ADMIN_PASS="${ADMIN_PASS:-change-me-admin}"

echo "Seeding historic personal finance via ${BACKEND_URL} ..."

COOKIE_JAR="$(mktemp)"
trap 'rm -f "$COOKIE_JAR"' EXIT

CSRF="$(
  curl -fsS -c "$COOKIE_JAR" -X POST "${BACKEND_URL}/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"username\":\"${ADMIN_USER}\",\"password\":\"${ADMIN_PASS}\"}" \
  | python3 -c 'import json,sys; print(json.load(sys.stdin)["csrf_token"])'
)"

curl -fsS -b "$COOKIE_JAR" -X POST "${BACKEND_URL}/finance/seed/historic" \
  -H "X-CSRF-Token: ${CSRF}" \
  | python3 -m json.tool

echo "Done."
