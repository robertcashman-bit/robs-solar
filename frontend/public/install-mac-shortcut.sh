#!/bin/bash
# Install a Mac Dock + Desktop Rob's Finance app that opens the live sign-in page.
# Does not need the All repo, npm, or localhost. Safe to run via:
#   curl -fsSL https://robs-solar.vercel.app/install-mac-shortcut.sh | bash
set -u

HOSTED_ORIGIN="${HOSTED_ROBS_FINANCE_ORIGIN:-https://robs-solar.vercel.app}"
LOGIN_URL="${HOSTED_ROBS_FINANCE_URL:-${HOSTED_ORIGIN}/login}"
APP_DIR="${HOME}/Applications/RobsFinance.app"
DESKTOP_DIR="${HOME}/Desktop"
DOWNLOADS_DIR="${HOME}/Downloads"
TEST_MODE="${INSTALL_MAC_SHORTCUT_TEST:-}"

if command -v osascript >/dev/null 2>&1; then
  finder_desktop="$(osascript -e 'POSIX path of (path to desktop folder)' 2>/dev/null | tr -d '\r' | sed 's:/*$::')"
  if [ -n "${finder_desktop}" ] && [ -d "${finder_desktop}" ]; then
    DESKTOP_DIR="${finder_desktop}"
  fi
fi

mkdir -p "${HOME}/Applications" "${DESKTOP_DIR}" "${DOWNLOADS_DIR}" \
  "${APP_DIR}/Contents/MacOS" "${APP_DIR}/Contents/Resources"

cat > "${APP_DIR}/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleDisplayName</key>
  <string>Rob's Finance</string>
  <key>CFBundleExecutable</key>
  <string>RobsFinance</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleIdentifier</key>
  <string>uk.cashman.robs-finance</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>RobsFinance</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>4.1</string>
  <key>CFBundleVersion</key>
  <string>4.1</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSSupportsAutomaticTermination</key>
  <false/>
</dict>
</plist>
EOF

cat > "${APP_DIR}/Contents/MacOS/RobsFinance" <<EOF
#!/bin/bash
set -uo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:\${PATH:-}"
if command -v open >/dev/null 2>&1; then
  exec open "${LOGIN_URL}"
fi
exit 1
EOF
chmod 755 "${APP_DIR}/Contents/MacOS/RobsFinance"

if command -v curl >/dev/null 2>&1; then
  curl -fsSL --max-time 20 "${HOSTED_ORIGIN}/icons/icon-512.png" \
    -o "${APP_DIR}/Contents/Resources/AppIcon.png" 2>/dev/null || true
fi

COMMAND_BODY="$(cat <<EOF
#!/bin/bash
if command -v open >/dev/null 2>&1; then
  exec open "${LOGIN_URL}"
fi
exit 1
EOF
)"

for dest in \
  "${DESKTOP_DIR}/RobsFinance.command" \
  "${HOME}/Desktop/RobsFinance.command" \
  "${DOWNLOADS_DIR}/RobsFinance.command"
do
  mkdir -p "$(dirname "${dest}")" 2>/dev/null || continue
  printf '%s\n' "${COMMAND_BODY}" > "${dest}"
  chmod 755 "${dest}"
  xattr -dr com.apple.quarantine "${dest}" 2>/dev/null || true
done

for dest in \
  "${DESKTOP_DIR}/RobsFinance.app" \
  "${HOME}/Desktop/RobsFinance.app"
do
  mkdir -p "$(dirname "${dest}")" 2>/dev/null || continue
  if [ -e "${dest}" ] && [ ! -L "${dest}" ]; then
    continue
  fi
  ln -sfn "${APP_DIR}" "${dest}"
done

xattr -dr com.apple.quarantine "${APP_DIR}" 2>/dev/null || true

if [ "$(uname -s)" = "Darwin" ] && [ -z "${TEST_MODE}" ]; then
  LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
  if [ -x "${LSREGISTER}" ]; then
    "${LSREGISTER}" -f "${APP_DIR}" >/dev/null 2>&1 || true
  fi
  PIN="$(mktemp /tmp/pin-rob-finance-dock.XXXXXX.py)"
  if command -v curl >/dev/null 2>&1 && curl -fsSL --max-time 20 \
    "${HOSTED_ORIGIN}/pin-rob-finance-dock.py" -o "${PIN}" 2>/dev/null; then
    ROB_FINANCE_APP="${APP_DIR}" python3 "${PIN}" || true
  fi
  rm -f "${PIN}"
  if command -v open >/dev/null 2>&1; then
    open "${LOGIN_URL}"
    open -R "${APP_DIR}" 2>/dev/null || true
  fi
fi

echo "Installed ${APP_DIR}"
echo "Desktop shortcut: ${DESKTOP_DIR}/RobsFinance.command"
echo "Opens ${LOGIN_URL}"
