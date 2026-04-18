#!/usr/bin/env bash
# Heimdall AI Automation — Uninstaller
# Usage: sudo bash uninstall.sh [--purge]
#   --purge  also removes .env, data/, config/, tasks/, workspace/, and venv
set -e

PURGE=false
for arg in "$@"; do
    [[ "$arg" == "--purge" ]] && PURGE=true
done

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Heimdall Uninstaller ==="
echo "→ Install directory: $INSTALL_DIR"
[[ "$PURGE" == "true" ]] && echo "→ Purge mode: runtime data will be deleted"
echo ""

# ── Systemd service ───────────────────────────────────────────────────────────

if systemctl is-active --quiet heimdall-backend 2>/dev/null; then
    systemctl stop heimdall-backend
    echo "✓ Service stopped"
fi

if systemctl is-enabled --quiet heimdall-backend 2>/dev/null; then
    systemctl disable heimdall-backend
    echo "✓ Service disabled"
fi

if [[ -f /etc/systemd/system/heimdall-backend.service ]]; then
    rm /etc/systemd/system/heimdall-backend.service
    systemctl daemon-reload
    echo "✓ Systemd unit removed"
fi

# ── CLI and desktop entry ─────────────────────────────────────────────────────

if [[ -f /usr/local/bin/heimdall ]]; then
    rm /usr/local/bin/heimdall
    echo "✓ heimdall CLI removed"
fi

if [[ -f /usr/share/applications/heimdall.desktop ]]; then
    rm /usr/share/applications/heimdall.desktop
    echo "✓ Desktop entry removed"
fi

# ── Purge (optional) ──────────────────────────────────────────────────────────

if [[ "$PURGE" == "true" ]]; then
    echo ""
    echo "Purging runtime data..."

    [[ -d "$INSTALL_DIR/backend/.venv" ]]   && rm -rf "$INSTALL_DIR/backend/.venv"   && echo "✓ Backend venv removed"
    [[ -d "$INSTALL_DIR/frontend/.next" ]]  && rm -rf "$INSTALL_DIR/frontend/.next"  && echo "✓ Frontend build removed"
    [[ -d "$INSTALL_DIR/frontend/node_modules" ]] && rm -rf "$INSTALL_DIR/frontend/node_modules" && echo "✓ node_modules removed"
    [[ -f "$INSTALL_DIR/.env" ]]            && rm "$INSTALL_DIR/.env"                && echo "✓ .env removed"
    [[ -d "$INSTALL_DIR/data" ]]            && rm -rf "$INSTALL_DIR/data"            && echo "✓ data/ removed (vault deleted)"
    [[ -d "$INSTALL_DIR/tasks" ]]           && rm -rf "$INSTALL_DIR/tasks"           && echo "✓ tasks/ removed"
    [[ -d "$INSTALL_DIR/workspace" ]]       && rm -rf "$INSTALL_DIR/workspace"       && echo "✓ workspace/ removed"

    echo ""
    echo "⚠  config/ was NOT removed — delete manually if you want to lose your settings:"
    echo "   rm -rf $INSTALL_DIR/config"
else
    echo ""
    echo "→ Runtime data kept (.env, data/, config/, tasks/, workspace/)."
    echo "  Re-run with --purge to also delete them."
fi

echo ""
echo "=== Heimdall uninstalled ==="
