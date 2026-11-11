#!/usr/bin/env bash
# OmniNet AI Agent Pro - Multiplatform POSIX Launcher (Linux / macOS / BSD)
# Auto-elevates to root if not already running as root.

set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"

# ============================================================
# AUTO-ELEVATION — re-exec with sudo if not root
# ============================================================
if [ "$EUID" -ne 0 ]; then
    echo "[OmniNet] Privilegios root requeridos. Re-ejecutando con sudo..."
    exec sudo bash "$0" "$@"
fi

echo "[OmniNet] Ejecutando con privilegios root (EUID=0). >>"

# ============================================================
# LAUNCH — prefer compiled binary, then system python
# ============================================================

# Standalone binary (Linux/macOS PyInstaller build)
if [ -f "$DIR/dist/OmniNet" ]; then
    exec "$DIR/dist/OmniNet" --no-elevate "$@"
fi

if [ -f "$DIR/OmniNet" ]; then
    exec "$DIR/OmniNet" --no-elevate "$@"
fi

# Virtual environment python
if [ -f "$DIR/.venv/bin/python3" ]; then
    exec "$DIR/.venv/bin/python3" "$DIR/main.py" --no-elevate "$@"
fi

# System python3
if command -v python3 >/dev/null 2>&1; then
    exec python3 "$DIR/main.py" --no-elevate "$@"
elif command -v python >/dev/null 2>&1; then
    exec python "$DIR/main.py" --no-elevate "$@"
else
    echo "[ERROR] Python 3 no encontrado en el sistema."
    echo "Instala Python 3.9+ con: apt install python3  |  brew install python3"
    exit 1
fi
