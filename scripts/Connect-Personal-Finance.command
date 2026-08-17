#!/bin/bash
# Double-click on the Mac: copy QuickFile from Custody Note if it is already
# on this machine. Does not invent balances or print secrets.
set -euo pipefail
cd "$(dirname "$0")"
exec ./connect-personal-finance.sh
