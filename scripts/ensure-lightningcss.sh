#!/usr/bin/env bash
# Apple Silicon Macs need both arm64 and x64 native binaries — Turbopack may load either.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" ]]; then
  exit 0
fi

pack_install() {
  local pkg="$1"
  local dest="$2"
  local version="$3"
  if [[ -d "$dest" ]]; then
    return 0
  fi
  local tgz="${pkg//\//-}-${version}.tgz"
  tgz="${tgz/@/}"
  npm pack "${pkg}@${version}" >/dev/null
  tar -xzf "$tgz"
  rm -rf "$dest"
  mv package "$dest"
  rm -f "$tgz"
}

read_version() {
  node -p "JSON.parse(require('fs').readFileSync('$1','utf8')).version"
}

LC_VERSION="$(read_version node_modules/lightningcss/package.json)"
pack_install "lightningcss-darwin-arm64" "node_modules/lightningcss-darwin-arm64" "$LC_VERSION"
pack_install "lightningcss-darwin-x64" "node_modules/lightningcss-darwin-x64" "$LC_VERSION"
ln -sf "../lightningcss-darwin-arm64/lightningcss.darwin-arm64.node" node_modules/lightningcss/lightningcss.darwin-arm64.node
ln -sf "../lightningcss-darwin-x64/lightningcss.darwin-x64.node" node_modules/lightningcss/lightningcss.darwin-x64.node

OX_VERSION="$(read_version node_modules/@tailwindcss/oxide/package.json)"
if [[ ! -d node_modules/@tailwindcss/oxide-darwin-arm64 ]]; then
  npm install "@tailwindcss/oxide-darwin-arm64@${OX_VERSION}" --force >/dev/null
fi
pack_install "@tailwindcss/oxide-darwin-x64" "node_modules/@tailwindcss/oxide-darwin-x64" "$OX_VERSION"
OX_DIR="node_modules/@tailwindcss/oxide"
ln -sf "../oxide-darwin-arm64/tailwindcss-oxide.darwin-arm64.node" "$OX_DIR/tailwindcss-oxide.darwin-arm64.node"
ln -sf "../oxide-darwin-x64/tailwindcss-oxide.darwin-x64.node" "$OX_DIR/tailwindcss-oxide.darwin-x64.node"

echo "Native CSS binaries ready (lightningcss + tailwind oxide, arm64 + x64)"
