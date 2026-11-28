# toktop installer for Windows. Nothing needs to be installed first. In PowerShell:
#   irm https://raw.githubusercontent.com/xlydevs/toktop/main/install.ps1 | iex
# It installs uv (a single program that brings its own Python), then toktop.
# Uninstall with: uv tool uninstall toktop

# "Continue": in Windows PowerShell 5, "Stop" turns any text a program writes to stderr into a fatal error
$ErrorActionPreference = "Continue"
$src = "https://github.com/xlydevs/toktop/archive/refs/heads/main.zip"

function Say($msg) { Write-Host "==> $msg" -ForegroundColor Yellow }
function Warn($msg) { Write-Host "==> $msg" -ForegroundColor Red }
function Have($name) { [bool](Get-Command $name -ErrorAction SilentlyContinue) }

# 1. uv
if (-not (Have "uv")) {
    Say "Installing uv (it brings its own Python, nothing else is needed)..."
    powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

# 2. toktop
Say "Installing toktop..."
uv tool install --force --python 3.12 --refresh-package toktop --reinstall-package toktop "toktop @ $src"
if ($LASTEXITCODE -ne 0) { Warn "toktop couldn't be installed (see the message above)."; return }
try { uv tool update-shell *> $null } catch { }

Say "Done. Open a new terminal and run: toktop"
Say "Just looking? Try: toktop --demo"
