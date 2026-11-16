#!/bin/sh
# Install terminal-terrarium from this offline bundle (no internet needed).
cd "$(dirname "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then exec python3 install.py "$@"; else exec python install.py "$@"; fi
