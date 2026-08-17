#!/bin/bash
# Double-click on the Mac: restore RobsFinance.app, Desktop shortcut, and Dock pin.
set -euo pipefail
cd "$(dirname "$0")"
exec ./build-mac-app.sh
