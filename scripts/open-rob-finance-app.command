#!/bin/bash
# Double-click: open the Rob Finance App workspace in Cursor.
set -euo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

home="${HOME:-/Users/robertcashman}"
_THIS="$(cd "$(dirname "$0")" && pwd)"

find_workspace() {
  local candidate
  if [[ -f "$_THIS/../rob-finance-app.code-workspace" ]]; then
    printf '%s\n' "$(cd "$_THIS/.." && pwd)/rob-finance-app.code-workspace"
    return 0
  fi
  if [[ -f "$_THIS/../../rob-finance-app.code-workspace" ]]; then
    printf '%s\n' "$(cd "$_THIS/../.." && pwd)/rob-finance-app.code-workspace"
    return 0
  fi
  for candidate in \
    "$home/All/rob-finance-app.code-workspace" \
    "$home/src/All/rob-finance-app.code-workspace" \
    "$home/Developer/All/rob-finance-app.code-workspace" \
    "$home/Documents/All/rob-finance-app.code-workspace" \
    "$home/code/All/rob-finance-app.code-workspace" \
    "$home/Projects/All/rob-finance-app.code-workspace" \
    "$home/repos/All/rob-finance-app.code-workspace" \
    "$home/GitHub/All/rob-finance-app.code-workspace" \
    "$home/robertdavidcashman-droid/All/rob-finance-app.code-workspace"
  do
    if [[ -f "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

WORKSPACE="$(find_workspace || true)"
if [[ -z "$WORKSPACE" ]]; then
  if command -v osascript >/dev/null 2>&1; then
    osascript -e 'display alert "Rob Finance App workspace not found" message "Clone github.com/robertdavidcashman-droid/All, then double-click this shortcut again."' 2>/dev/null || true
  fi
  exit 1
fi

if command -v open >/dev/null 2>&1; then
  open -b com.todesktop.230313mzl4w4u92 "$WORKSPACE" 2>/dev/null && exit 0
  open -a Cursor "$WORKSPACE" 2>/dev/null && exit 0
  open "$WORKSPACE" && exit 0
fi
exit 1
