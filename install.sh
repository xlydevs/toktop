#!/bin/sh
# toktop installer for macOS and Linux. Nothing needs to be installed first:
#   curl -LsSf https://raw.githubusercontent.com/xlydevs/toktop/main/install.sh | sh
# It installs uv (a single program that brings its own Python), then toktop.
# Uninstall with: uv tool uninstall toktop
set -eu

SRC="https://github.com/xlydevs/toktop/archive/refs/heads/main.tar.gz"

say() { printf '\033[1;33m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;31m==>\033[0m %s\n' "$1"; }
have() { command -v "$1" >/dev/null 2>&1; }

if ! have curl; then
    warn "curl is needed to install toktop. Install it with your system's package manager and run this again."
    exit 1
fi

# 1. uv
if ! have uv; then
    say "Installing uv (it brings its own Python, nothing else is needed)…"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
    export PATH
fi

# 2. toktop
say "Installing toktop…"
uv tool install --force --python 3.12 --refresh-package toktop --reinstall-package toktop "toktop @ $SRC"
uv tool update-shell >/dev/null 2>&1 || true

say "Done. Open a new terminal and run: toktop"
say "Just looking? Try: toktop --demo"
