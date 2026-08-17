# Install a Desktop shortcut that opens Rob's Finance sign-in.
# Safe to run via:
#   irm https://robs-solar.vercel.app/install-windows-shortcut.ps1 | iex
$ErrorActionPreference = "Stop"
$loginUrl = "https://robs-solar.vercel.app/login?send=1"
$desktop = [Environment]::GetFolderPath("Desktop")
if (-not $desktop) {
  $desktop = Join-Path $env:USERPROFILE "Desktop"
}
New-Item -ItemType Directory -Force -Path $desktop | Out-Null
$dest = Join-Path $desktop "Robs Finance.url"
@(
  "[InternetShortcut]"
  "URL=$loginUrl"
) | Set-Content -Path $dest -Encoding ASCII
Write-Host "Desktop shortcut: $dest"
Write-Host "Opens $loginUrl"
if (Test-Path $dest) {
  Start-Process $dest
}
