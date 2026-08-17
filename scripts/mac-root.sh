#!/usr/bin/env bash
# Shared path resolution for Rob's Finance. Prefer the All monorepo checkout.
# Do not clone, open browsers, or prompt — launchers must work unattended.

_mac_home() {
  printf '%s\n' "${HOME:-/Users/robertcashman}"
}

_all_candidate_solar_roots() {
  local home
  home="$(_mac_home)"
  printf '%s\n' \
    "$home/All/robs-solar" \
    "$home/src/All/robs-solar" \
    "$home/Developer/All/robs-solar" \
    "$home/Documents/All/robs-solar" \
    "$home/code/All/robs-solar" \
    "$home/Projects/All/robs-solar" \
    "$home/repos/All/robs-solar" \
    "$home/GitHub/All/robs-solar" \
    "$home/robertdavidcashman-droid/All/robs-solar" \
    "$home/workspace/robs-solar" \
    "$home/robs-solar"
}

_looks_like_solar_root() {
  local candidate="$1"
  [[ -d "$candidate/backend" && -d "$candidate/frontend" && -f "$candidate/scripts/mac-launch.sh" ]] || return 1
  # Old standalone checkouts still ship Energy pages. Never launch those.
  if [[ -d "$candidate/frontend/src/app/(energy)" ]]; then
    return 1
  fi
  return 0
}

_spotlight_solar_root() {
  command -v mdfind >/dev/null 2>&1 || return 1
  local ws solar
  while IFS= read -r ws; do
    [[ -z "$ws" || ! -f "$ws" ]] && continue
    solar="$(dirname "$ws")/robs-solar"
    if _looks_like_solar_root "$solar"; then
      printf '%s\n' "$solar"
      return 0
    fi
  done < <(mdfind 'kMDItemFSName == "rob-finance-app.code-workspace"' 2>/dev/null)
  return 1
}

read_baked_project_root() {
  local baked="$1"
  [[ -f "$baked" ]] || return 1
  local value
  value="$(tr -d '\r' <"$baked" | head -n 1)"
  if _looks_like_solar_root "$value"; then
    printf '%s\n' "$value"
    return 0
  fi
  return 1
}

resolve_robs_solar_root() {
  if [[ -n "${ROBS_SOLAR_ROOT:-}" ]] && _looks_like_solar_root "${ROBS_SOLAR_ROOT}"; then
    printf '%s\n' "$ROBS_SOLAR_ROOT"
    return 0
  fi
  local candidate
  while IFS= read -r candidate; do
    if _looks_like_solar_root "$candidate"; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done < <(_all_candidate_solar_roots)
  _spotlight_solar_root
}

robs_finance_log_dir() {
  if [[ "$(uname -s)" == "Darwin" ]]; then
    printf '%s\n' "$(_mac_home)/Library/Logs/RobsFinance"
  elif [[ -d "$(_mac_home)/Library" || "$(uname -s)" == "Darwin" ]]; then
    printf '%s\n' "$(_mac_home)/Library/Logs/RobsFinance"
  else
    # Keep the Mac path when we can create it; otherwise use XDG.
    if mkdir -p "$(_mac_home)/Library/Logs/RobsFinance" 2>/dev/null; then
      printf '%s\n' "$(_mac_home)/Library/Logs/RobsFinance"
    else
      printf '%s\n' "$(_mac_home)/.local/share/robs-finance/logs"
    fi
  fi
}

write_backend_launch_agent() {
  local root="$1"
  local dst="${2:-$HOME/Library/LaunchAgents/com.robssolar.backend.plist}"
  mkdir -p "$(dirname "$dst")"
  cat >"$dst" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.robssolar.backend</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${root}/scripts/backend-service.sh</string>
    </array>
    <key>EnvironmentVariables</key>
    <dict>
        <key>ROBS_SOLAR_ROOT</key>
        <string>${root}</string>
        <key>PATH</key>
        <string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>WorkingDirectory</key>
    <string>${root}/backend</string>
    <key>RunAtLoad</key>
    <false/>
    <key>KeepAlive</key>
    <false/>
    <key>ThrottleInterval</key>
    <integer>5</integer>
    <key>StandardOutPath</key>
    <string>${root}/.backend-service.log</string>
    <key>StandardErrorPath</key>
    <string>${root}/.backend-service.log</string>
</dict>
</plist>
EOF
}

HOSTED_ROBS_FINANCE_URL="${HOSTED_ROBS_FINANCE_URL:-https://robs-solar.vercel.app/login?send=1}"

open_hosted_robs_finance() {
  # Used when the local All checkout / RobsFinance.app is missing so the
  # Dock and Desktop icons open Finance instead of bouncing.
  if command -v open >/dev/null 2>&1; then
    open "${HOSTED_ROBS_FINANCE_URL}"
    return 0
  fi
  return 1
}
