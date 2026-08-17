#!/usr/bin/env python3
"""Pin RobsFinance.app to the Dock without rewriting unrelated Dock items.

Rewriting com.apple.dock wholesale created "?" ghost tiles.
This only removes stale Rob tiles and array-adds one file URL.
The app path must not contain an apostrophe (use RobsFinance.app).
"""

from __future__ import annotations

import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse


def _url_for(path: Path) -> str:
    uri = path.expanduser().resolve().as_uri()
    return uri if uri.endswith("/") else uri + "/"


def _tile_blob(tile: object) -> str:
    return repr(tile).lower()


def _is_rob_tile(tile: object) -> bool:
    blob = _tile_blob(tile)
    return any(
        token in blob
        for token in (
            "rob's solar.app",
            "robs solar.app",
            "/robs-solar.app",
            "rob's finance.app",
            "robs finance.app",
            "robsfinance.app",
            "uk.cashman.robs-finance",
            "uk.cashman.robs-solar",
        )
    )


def _path_from_tile(tile: object) -> Path | None:
    if not isinstance(tile, dict):
        return None
    data = tile.get("tile-data") or {}
    file_data = data.get("file-data") or {}
    url = str(file_data.get("_CFURLString") or "")
    if not url.startswith("file://"):
        return None
    parsed = urlparse(url)
    local = unquote(parsed.path)
    if local.endswith("/"):
        local = local[:-1]
    return Path(local) if local else None


def _is_broken_file_tile(tile: object) -> bool:
    if not isinstance(tile, dict):
        return False
    data = tile.get("tile-data") or {}
    file_data = data.get("file-data") or {}
    url = str(file_data.get("_CFURLString") or "")
    if not url:
        return False
    if "%2f" in url.lower() and url.lower().startswith("file://%2f"):
        return True
    path = _path_from_tile(tile)
    return path is not None and not path.exists()


def _same_path(left: Path, right: Path) -> bool:
    try:
        return left.expanduser().resolve() == right.expanduser().resolve()
    except OSError:
        return left == right


def _tile_points_at_app(tile: object, app_path: Path) -> bool:
    """True when the Dock tile already opens this app, even if the URL spelling differs."""
    path = _path_from_tile(tile)
    if path is not None and _same_path(path, app_path):
        return True
    if _is_broken_file_tile(tile):
        return False
    if not isinstance(tile, dict):
        return False
    ident = str((tile.get("tile-data") or {}).get("bundle-identifier") or "")
    return ident == "uk.cashman.robs-finance"


def _finance_tile(app_path: Path) -> dict:
    return {
        "tile-data": {
            "file-data": {
                "_CFURLString": _url_for(app_path),
                "_CFURLStringType": 15,
            },
            "file-label": "RobsFinance",
            "file-type": 41,
            "bundle-identifier": "uk.cashman.robs-finance",
        },
        "tile-type": "file-tile",
    }


def self_test() -> int:
    url = _url_for(Path("/Users/test/Applications/RobsFinance.app"))
    expected = "file:///Users/test/Applications/RobsFinance.app/"
    if url != expected:
        print(f"FAIL Dock URL {url!r} != {expected!r}", file=sys.stderr)
        return 1
    if "'" in url or "%2F" in url or "%2f" in url:
        print(f"FAIL Dock URL is unsafe: {url}", file=sys.stderr)
        return 1
    app = Path("/Users/test/Applications/RobsFinance.app")
    tile = _finance_tile(app)
    noslash = {
        "tile-data": {
            "file-data": {
                "_CFURLString": "file:///Users/test/Applications/RobsFinance.app",
                "_CFURLStringType": 15,
            },
            "bundle-identifier": "uk.cashman.robs-finance",
        },
        "tile-type": "file-tile",
    }
    encoded = {
        "tile-data": {
            "file-data": {
                "_CFURLString": "file://%2FUsers%2Ftest%2FApplications%2FRobsFinance.app/",
                "_CFURLStringType": 15,
            }
        },
        "tile-type": "file-tile",
    }
    if not _tile_points_at_app(tile, app):
        print("FAIL generated tile should match the app path", file=sys.stderr)
        return 1
    if not _tile_points_at_app(noslash, app):
        print("FAIL tile without trailing slash should still match", file=sys.stderr)
        return 1
    if _tile_points_at_app(encoded, app):
        print("FAIL encoded file://%2F tile must be treated as broken", file=sys.stderr)
        return 1
    print(f"ok   - Dock pin URL {url}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Pin RobsFinance.app to the Dock")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()

    if sys.platform != "darwin":
        print("pin-rob-finance-dock.py is for macOS only")
        return 0

    app = Path(
        os.environ.get(
            "ROB_FINANCE_APP",
            str(Path.home() / "Applications" / "RobsFinance.app"),
        )
    )
    if not app.exists():
        print(f"App not found: {app}", file=sys.stderr)
        return 1

    lsregister = (
        "/System/Library/Frameworks/CoreServices.framework/Frameworks/"
        "LaunchServices.framework/Support/lsregister"
    )
    if Path(lsregister).exists():
        subprocess.run([lsregister, "-f", str(app)], check=False)

    export = subprocess.check_output(["defaults", "export", "com.apple.dock", "-"])
    data = plistlib.loads(export)
    apps = list(data.get("persistent-apps") or [])
    rob_tiles = [tile for tile in apps if _is_rob_tile(tile)]
    correct_single = len(rob_tiles) == 1 and _tile_points_at_app(rob_tiles[0], app)
    if correct_single:
        print(f"Dock already points at {app}")
        return 0

    kept = [tile for tile in apps if not _is_rob_tile(tile) and not _is_broken_file_tile(tile)]
    kept.append(_finance_tile(app))
    data["persistent-apps"] = kept

    imported = plistlib.dumps(data, fmt=plistlib.FMT_BINARY)
    subprocess.run(
        ["defaults", "import", "com.apple.dock", "-"],
        input=imported,
        check=True,
    )
    subprocess.run(["killall", "Dock"], check=False)
    print(f"Dock now points at {app}")
    print(f"Dock URL: {_url_for(app)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
