#!/usr/bin/env bash
# One-command end-to-end demo (Linux/macOS/Git-Bash).
# Boots all 3 services, seeds, and runs the agent happy path + extras.
set -euo pipefail

cd "$(dirname "$0")/.."

if [ -d "venv/Scripts" ]; then
  PY="venv/Scripts/python.exe"   # Windows venv layout
elif [ -d "venv/bin" ]; then
  PY="venv/bin/python"           # POSIX venv layout
else
  PY="python"
fi

exec "$PY" -m scripts.run_demo
