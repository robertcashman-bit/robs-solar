#!/usr/bin/env bash
# Install RobsFinance.app (no apostrophe — Dock "?" tiles come from
# Rob's Finance.app paths), restore the Desktop shortcut, and pin the Dock.
# Display name stays "Rob's Finance".
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=mac-root.sh
source "$ROOT/scripts/mac-root.sh"
# shellcheck source=visible-desktop.sh
source "$ROOT/scripts/visible-desktop.sh"

if [[ -d "$ROOT/backend" && -d "$ROOT/frontend" ]]; then
  :
else
  CHECKOUT="$(resolve_robs_solar_root || true)"
  ROOT="${CHECKOUT:-$ROOT}"
fi

ICON_SRC="${ICON_SRC:-$ROOT/scripts/assets/rob-finance-icon.png}"
if [[ ! -f "$ICON_SRC" && -f "$ROOT/frontend/public/icons/icon-512.png" ]]; then
  ICON_SRC="$ROOT/frontend/public/icons/icon-512.png"
fi
if [[ ! -f "$ICON_SRC" ]]; then
  echo "Icon not found: $ICON_SRC" >&2
  exit 1
fi

# No apostrophe / no spaces in the bundle name. CFBundleDisplayName stays "Rob's Finance".
APP_DIR="$HOME/Applications/RobsFinance.app"
if [[ -w /Applications ]] || mkdir -p /Applications 2>/dev/null; then
  if [[ -w /Applications ]]; then
    APP_DIR="/Applications/RobsFinance.app"
  fi
fi
mkdir -p "$(dirname "$APP_DIR")"

TEMPLATE="$ROOT/macos/RobsFinance.app"
mkdir -p "$TEMPLATE/Contents/MacOS" "$TEMPLATE/Contents/Resources"

cat > "$TEMPLATE/Contents/Info.plist" <<'EOF'
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
  <string>4.0</string>
  <key>CFBundleVersion</key>
  <string>4.0</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSSupportsAutomaticTermination</key>
  <false/>
</dict>
</plist>
EOF

cat > "$TEMPLATE/Contents/MacOS/RobsFinance" <<'EOF'
#!/bin/bash
# Rob's Finance.app entry point. Prefer the baked project path, then search.
set -uo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"

BUNDLE="$(cd "$(dirname "$0")/../.." && pwd)"
BAKED="$BUNDLE/Contents/Resources/project-root"
ROOT=""
if [[ -f "$BAKED" ]]; then
  ROOT="$(tr -d '\r' <"$BAKED" | head -n 1)"
fi
if [[ -z "$ROOT" || ! -x "$ROOT/scripts/mac-launch.sh" ]]; then
  home="${HOME:-/Users/robertcashman}"
  for candidate in \
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
  do
    if [[ -x "$candidate/scripts/mac-launch.sh" && -d "$candidate/backend" && ! -d "$candidate/frontend/src/app/(energy)" ]]; then
      ROOT="$candidate"
      break
    fi
  done
fi

if [[ -z "$ROOT" || ! -x "$ROOT/scripts/mac-launch.sh" ]]; then
  if command -v open >/dev/null 2>&1; then
    exec open "https://robs-solar.vercel.app/login"
  fi
  if [[ -x /usr/bin/osascript ]]; then
    /usr/bin/osascript -e 'display alert "Rob'\''s Finance could not start" message "The project folder was not found. Open https://robs-solar.vercel.app or install from that site."' 2>/dev/null || true
  fi
  exit 1
fi

export ROBS_SOLAR_ROOT="$ROOT"
export ROBS_FINANCE_APP_BUNDLE="$BUNDLE"
exec /bin/bash "$ROOT/scripts/mac-launch.sh"
EOF
chmod 755 "$TEMPLATE/Contents/MacOS/RobsFinance"
cp "$ICON_SRC" "$TEMPLATE/Contents/Resources/AppIcon.png"
printf '%s\n' "$ROOT" > "$TEMPLATE/Contents/Resources/project-root"

# Remove broken Application bundles first. Desktop aliases wait until the new
# shortcut exists so a failed rewrite cannot leave the Desktop empty.
OLD_APP_BUNDLES=(
  "$HOME/Applications/Rob's Finance.app"
  "$HOME/Applications/Rob's Solar.app"
  "$HOME/Applications/Robs Finance.app"
  "/Applications/Rob's Finance.app"
  "/Applications/Rob's Solar.app"
  "/Applications/Robs Finance.app"
)
for old in "${OLD_APP_BUNDLES[@]}"; do
  if [[ -e "$old" ]]; then
    rm -rf "$old"
    echo "Removed $old"
  fi
done

app_already_installed() {
  [[ -x "$APP_DIR/Contents/MacOS/RobsFinance" ]] || return 1
  [[ -f "$APP_DIR/Contents/Info.plist" ]] || return 1
  grep -q 'uk.cashman.robs-finance' "$APP_DIR/Contents/Info.plist" || return 1
  [[ -f "$APP_DIR/Contents/Resources/project-root" ]] || return 1
  [[ "$(tr -d '\r' <"$APP_DIR/Contents/Resources/project-root" | head -n 1)" == "$ROOT" ]]
}

if app_already_installed; then
  echo "App already installed at $APP_DIR — skipping rewrite"
else
  rm -rf "$APP_DIR"
  mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"
  cp "$TEMPLATE/Contents/Info.plist" "$APP_DIR/Contents/Info.plist"
  cp "$TEMPLATE/Contents/MacOS/RobsFinance" "$APP_DIR/Contents/MacOS/RobsFinance"
  cp "$TEMPLATE/Contents/Resources/AppIcon.png" "$APP_DIR/Contents/Resources/AppIcon.png"
  printf '%s\n' "$ROOT" > "$APP_DIR/Contents/Resources/project-root"
  chmod 755 "$APP_DIR/Contents/MacOS/RobsFinance"
fi

remove_stale_desktop_launchers() {
  local old
  for old in \
    "$HOME/Desktop/Rob's Finance.app" \
    "$HOME/Desktop/Rob's Solar.app" \
    "$HOME/Desktop/Robs Finance.app" \
    "$HOME/Desktop/Rob's Finance" \
    "$HOME/Desktop/Rob's Solar"
  do
    if [[ -e "$old" || -L "$old" ]]; then
      rm -rf "$old"
      echo "Removed $old"
    fi
  done
}

install_desktop_shortcuts() {
  local src="$ROOT/scripts/desktop-robs-finance.command"
  local workspace_src="$ROOT/scripts/open-rob-finance-app.command"
  local desktop_dir desktop_cmd desktop_app
  [[ -f "$src" ]] || return 0
  desktop_dir="$(finder_desktop_dir)"
  mkdir -p "$desktop_dir" "$HOME/Desktop" "$HOME/Downloads"
  desktop_cmd="$desktop_dir/RobsFinance.command"
  place_visible_shortcut "$src" "RobsFinance.command" >/dev/null || true
  cp "$src" "$desktop_cmd"
  chmod 755 "$desktop_cmd"
  desktop_app="$(place_visible_app_symlink "$APP_DIR" "RobsFinance.app" || true)"
  if [[ -f "$workspace_src" ]]; then
    place_visible_shortcut "$workspace_src" "Rob Finance App.command" >/dev/null || true
  fi
  if [[ "$(uname -s)" == "Darwin" ]]; then
    /usr/bin/osascript <<EOF >/dev/null 2>&1 || true
tell application "Finder"
  set destFolder to POSIX file "$desktop_dir" as alias
  set srcApp to POSIX file "$APP_DIR" as alias
  try
    delete file "Robs Finance" of destFolder
  end try
  try
    make new alias file at destFolder to srcApp with properties {name:"Robs Finance"}
  end try
end tell
EOF
    xattr -dr com.apple.quarantine "$desktop_cmd" 2>/dev/null || true
    reveal_shortcut "${desktop_app:-$desktop_cmd}" || true
  fi
  if [[ -e "$desktop_cmd" || -L "$desktop_dir/RobsFinance.app" || -n "$desktop_app" ]]; then
    remove_stale_desktop_launchers
  fi
  echo "Desktop shortcut: $desktop_cmd"
  echo "Desktop app shortcut: ${desktop_app:-$desktop_dir/RobsFinance.app}"
}

if [[ "$(uname -s)" == "Darwin" ]]; then
  if ! app_already_installed || [[ ! -f "$APP_DIR/Contents/Resources/AppIcon.icns" ]]; then
    ICONSET="/tmp/robs-finance.iconset"
    ICNS="/tmp/robs-finance.icns"
    rm -rf "$ICONSET" "$ICNS"
    mkdir -p "$ICONSET"
    if command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
      for size in 16 32 128 256 512; do
        sips -z "$size" "$size" "$ICON_SRC" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
        double=$((size * 2))
        sips -z "$double" "$double" "$ICON_SRC" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
      done
      iconutil -c icns "$ICONSET" -o "$ICNS"
      cp "$ICNS" "$APP_DIR/Contents/Resources/AppIcon.icns"
      cp "$ICNS" "$TEMPLATE/Contents/Resources/AppIcon.icns"
    fi
    xattr -dr com.apple.quarantine "$APP_DIR" 2>/dev/null || true
    if command -v codesign >/dev/null 2>&1; then
      codesign --force --deep --sign - "$APP_DIR" >/dev/null 2>&1 || true
    fi
  fi
  LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
  if [[ -x "$LSREGISTER" ]]; then
    "$LSREGISTER" -f "$APP_DIR" >/dev/null 2>&1 || true
  fi

  # Prefer the Python pin helper: it no-ops when the Dock tile is already correct.
  # Avoid dockutil add + Dock restart on every workspace folderOpen.
  export ROB_FINANCE_APP="$APP_DIR"
  python3 "$ROOT/scripts/pin-rob-finance-dock.py" || true
else
  echo "Not macOS — installed a local app bundle for launch testing."
  echo "Dock pin requires Darwin and will run automatically when this script is opened on the Mac."
fi

if [[ ! -x "$APP_DIR/Contents/MacOS/RobsFinance" ]]; then
  echo "ERROR: RobsFinance.app bundle is incomplete at $APP_DIR" >&2
  exit 1
fi

install_desktop_shortcuts

echo "Installed $APP_DIR"
echo "Display name: Rob's Finance"
echo "Project path: $ROOT"
echo "$APP_DIR" > "$ROOT/.installed-app-path"
