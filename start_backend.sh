#!/bin/bash
# Start Heimdall backend
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Run from project root so .env relative paths (config/, data/) resolve correctly
cd "$SCRIPT_DIR"

# Create venv if it doesn't exist
if [ ! -d "backend/.venv" ]; then
    echo "Creating virtual environment..."
    python -m venv backend/.venv
fi

# Activate venv
source backend/.venv/bin/activate

# Install requirements if requirements.txt is newer than the marker (or marker absent)
if [ ! -f "backend/.venv/requirements_installed" ] || [ "backend/requirements.txt" -nt "backend/.venv/requirements_installed" ]; then
    echo "Installing requirements..."
    pip install -r backend/requirements.txt
    touch backend/.venv/requirements_installed
fi

# Start backend
echo "Starting backend..."
trap 'echo ""; echo "Backend stopped cleanly."' SIGINT SIGTERM

python backend/main.py
