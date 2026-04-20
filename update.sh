#!/usr/bin/env bash
# Heimdall AI Automation — Updater
# Usage: bash update.sh
#   or via CLI: heimdall update
#
# Steps: git pull → pip install → npm build → service restart → health check
set -euo pipefail

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORCE=false
for arg in "$@"; do [[ "$arg" == "--force" ]] && FORCE=true; done

echo "=== Heimdall Update ==="
echo "→ Install directory: $INSTALL_DIR"
echo ""

# ── 1. git pull ────────────────────────────────────────────────────────────────

echo "→ Pulling latest code…"
cd "$INSTALL_DIR"
git fetch --all
PULL_OUT=$(git pull --ff-only 2>&1)
echo "$PULL_OUT"

if echo "$PULL_OUT" | grep -q "Already up to date" && [[ "$FORCE" == "false" ]]; then
    echo ""
    echo "✓ Already up to date — no rebuild needed."
    echo "  Run 'heimdall update --force' to rebuild anyway."
    exit 0
fi
echo "✓ Code updated"

# ── 2. pip install ─────────────────────────────────────────────────────────────

VENV_PIP="$INSTALL_DIR/backend/.venv/bin/pip"
if [[ ! -f "$VENV_PIP" ]]; then
    VENV_PIP=$(which pip3 2>/dev/null || which pip)
fi

echo ""
echo "→ Updating Python dependencies…"
"$VENV_PIP" install -r "$INSTALL_DIR/backend/requirements.txt" -q
echo "✓ Python dependencies up to date"

# ── 3. npm install + build ─────────────────────────────────────────────────────

echo ""
echo "→ Installing frontend packages…"
cd "$INSTALL_DIR/frontend"
npm install --prefer-offline
echo "✓ Packages installed"

echo ""
echo "→ Building frontend (this may take 1-3 minutes)…"
rm -rf .next out
npm run build
echo "✓ Frontend built"
cd "$INSTALL_DIR"

# ── 4. Restart service ─────────────────────────────────────────────────────────

echo ""
echo "→ Restarting Heimdall service…"

if systemctl is-active --quiet heimdall-backend 2>/dev/null; then
    sudo systemctl restart heimdall-backend
    echo "✓ Service restarted via systemd"
else
    # Fallback: kill any uvicorn process on the heimdall port
    PORT=${PORT:-8000}
    PIDS=$(ss -tlnp "sport = :${PORT}" 2>/dev/null | grep -oP 'pid=\K[0-9]+' || true)
    if [[ -n "$PIDS" ]]; then
        for pid in $PIDS; do
            kill -TERM "$pid" 2>/dev/null || true
            echo "→ Sent SIGTERM to pid $pid"
        done
    else
        echo "⚠  No running service found — start it manually: heimdall start"
        exit 0
    fi
fi

# ── 5. Health check ────────────────────────────────────────────────────────────

echo ""
echo "→ Waiting for service to come back up…"
HOST=${HOST:-localhost}
URL="http://${HOST}:${PORT}/api/health"
for i in {1..30}; do
    if curl -sf "$URL" > /dev/null 2>&1; then
        echo "✓ Heimdall is up at http://${HOST}:${PORT}"
        echo ""
        echo "=== Update complete ==="
        exit 0
    fi
    sleep 2
done

echo "⚠  Service did not respond after 60s — check: journalctl -u heimdall-backend"
exit 1
