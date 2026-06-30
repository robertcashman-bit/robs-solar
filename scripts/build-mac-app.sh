#!/usr/bin/env bash
# Build Rob's Solar.app with the premium sun+panel icon and pin to Dock.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ICON_SRC="${ICON_SRC:-$HOME/.cursor/projects/Users-robertcashman-robs-solar/assets/solar-icon-1-sun-panel.png}"
APP_DIR="$HOME/Applications/Rob's Solar.app"
ICONSET="/tmp/robs-solar.iconset"
ICNS="/tmp/robs-solar.icns"

if [[ ! -f "$ICON_SRC" ]]; then
  echo "Icon not found: $ICON_SRC" >&2
  exit 1
fi

mkdir -p "$HOME/Applications"
rm -rf "$ICONSET" "$ICNS" "$APP_DIR"
mkdir -p "$ICONSET"

for size in 16 32 128 256 512; do
  sips -z "$size" "$size" "$ICON_SRC" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  double=$((size * 2))
  sips -z "$double" "$double" "$ICON_SRC" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$ICNS"

mkdir -p "$APP_DIR/Contents/MacOS" "$APP_DIR/Contents/Resources"
cp "$ICNS" "$APP_DIR/Contents/Resources/AppIcon.icns"

cat > "$APP_DIR/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleExecutable</key>
  <string>launch</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleIdentifier</key>
  <string>uk.cashman.robs-solar</string>
  <key>CFBundleName</key>
  <string>Rob's Solar</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
</dict>
</plist>
EOF

cp "$ROOT/scripts/mac-launch.sh" "$APP_DIR/Contents/MacOS/launch"
chmod +x "$APP_DIR/Contents/MacOS/launch"

# Pin to Dock (append if not already present)
APP_PATH="$APP_DIR"
if ! /usr/libexec/PlistBuddy -c "Print :persistent-apps" "$HOME/Library/Preferences/com.apple.dock.plist" 2>/dev/null | grep -q "Rob's Solar.app"; then
  defaults write com.apple.dock persistent-apps -array-add "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>file://$APP_PATH/</string><key>_CFURLStringType</key><integer>0</integer></dict></dict></dict>"
  killall Dock 2>/dev/null || true
fi

echo "Built $APP_DIR and pinned to Dock."
