#!/bin/bash
# Start Heimdall frontend
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/frontend"

# Install dependencies if package.json is newer than the marker (or marker absent)
INSTALL_MARKER="node_modules/.install_ok"
if [ ! -f "$INSTALL_MARKER" ] || [ package.json -nt "$INSTALL_MARKER" ] || { [ -f "package-lock.json" ] && [ "package-lock.json" -nt "$INSTALL_MARKER" ]; }; then
    echo "Installing dependencies..."
    npm install
    touch "$INSTALL_MARKER"
fi

# Start dev server
echo "Starting frontend..."
trap 'echo ""; echo "Frontend stopped cleanly."; exit 0' SIGINT SIGTERM

npm run dev
