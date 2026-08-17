#!/bin/bash
# Resolve the Desktop Finder actually shows (iCloud Desktop is often not $HOME/Desktop).

finder_desktop_dir() {
  local d=""
  if command -v osascript >/dev/null 2>&1; then
    d="$(osascript -e 'POSIX path of (path to desktop folder)' 2>/dev/null | tr -d '\r' | sed 's:/*$::')"
  fi
  if [ -n "${d}" ] && [ -d "${d}" ]; then
    printf '%s\n' "${d}"
    return 0
  fi
  printf '%s\n' "${HOME}/Desktop"
}

each_shortcut_dir() {
  local d=""
  finder_desktop_dir
  printf '%s\n' "${HOME}/Desktop"
  printf '%s\n' "${HOME}/Downloads"
  d="${HOME}/Library/Mobile Documents/com~apple~CloudDocs/Desktop"
  if [ -d "${d}" ]; then
    printf '%s\n' "${d}"
  fi
}

place_visible_shortcut() {
  local src="$1"
  local name="${2:-RobsFinance.command}"
  local dest d placed=""
  [ -f "${src}" ] || return 1
  while IFS= read -r d; do
    [ -n "${d}" ] || continue
    mkdir -p "${d}" 2>/dev/null || continue
    dest="${d}/${name}"
    cp "${src}" "${dest}"
    chmod 755 "${dest}"
    xattr -dr com.apple.quarantine "${dest}" 2>/dev/null || true
    if [ -z "${placed}" ]; then
      placed="${dest}"
    fi
  done < <(each_shortcut_dir | awk 'NF && !seen[$0]++')
  [ -n "${placed}" ] || return 1
  printf '%s\n' "${placed}"
}

place_visible_app_symlink() {
  local app="$1"
  local name="${2:-RobsFinance.app}"
  local dest d placed=""
  [ -e "${app}" ] || return 1
  while IFS= read -r d; do
    [ -n "${d}" ] || continue
    mkdir -p "${d}" 2>/dev/null || continue
    dest="${d}/${name}"
    if [ -e "${dest}" ] && [ ! -L "${dest}" ]; then
      continue
    fi
    ln -sfn "${app}" "${dest}"
    if [ -z "${placed}" ]; then
      placed="${dest}"
    fi
  done < <(each_shortcut_dir | awk 'NF && !seen[$0]++')
  [ -n "${placed}" ] || return 1
  printf '%s\n' "${placed}"
}

reveal_shortcut() {
  local path="$1"
  [ -e "${path}" ] || return 1
  if command -v open >/dev/null 2>&1; then
    open -R "${path}" 2>/dev/null || open -a Finder "${path}" 2>/dev/null || true
  fi
}
