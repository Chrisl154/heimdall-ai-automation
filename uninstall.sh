#!/usr/bin/env bash
# Heimdall AI Automation — Uninstaller
# Usage: sudo bash uninstall.sh [--purge]
#
# Default  — stops/disables services, removes CLI, service files, desktop entry.
#            Keeps .env, data/, config/, tasks/, workspace/, venv, node_modules.
# --purge  — everything above plus all runtime data, build artifacts, and the
#            entire install directory if it was placed at /opt/heimdall.
set -euo pipefail

# ── Root check ────────────────────────────────────────────────────────────────

if [[ $EUID -ne 0 ]]; then
    echo "✗ This script must be run as root:  sudo bash uninstall.sh"
    exit 1
fi

# ── Args ─────────────────────────────────────────────────────────────────────

PURGE=false
for arg in "$@"; do
    [[ "$arg" == "--purge" ]] && PURGE=true
done

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Heimdall Uninstaller ==="
echo "→ Install directory: $INSTALL_DIR"
[[ "$PURGE" == "true" ]] && echo "→ Purge mode ON — all data will be deleted"
echo ""

# ── Stop and disable systemd services ────────────────────────────────────────

for svc in heimdall-frontend heimdall-backend; do
    # Reset failed state so stop/disable work cleanly
    systemctl reset-failed "$svc" 2>/dev/null || true

    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        echo "→ Stopping $svc..."
        systemctl stop "$svc" 2>/dev/null || true
        # Wait up to 10 s for it to actually stop
        for i in {1..10}; do
            systemctl is-active --quiet "$svc" 2>/dev/null || break
            sleep 1
        done
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            echo "⚠  $svc did not stop cleanly — sending SIGKILL..."
            systemctl kill --signal=SIGKILL "$svc" 2>/dev/null || true
        fi
        echo "✓ $svc stopped"
    fi

    if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
        systemctl disable "$svc" 2>/dev/null || true
        echo "✓ $svc disabled"
    fi

    if [[ -f "/etc/systemd/system/${svc}.service" ]]; then
        rm -f "/etc/systemd/system/${svc}.service"
        echo "✓ ${svc}.service removed"
    fi
done

systemctl daemon-reload
systemctl reset-failed 2>/dev/null || true

# ── Kill any lingering processes on heimdall ports ────────────────────────────
# Catches processes that were started outside of systemd (e.g. manual runs).

for port in 8000 3000; do
    PIDS=$(ss -tlnp "sport = :${port}" 2>/dev/null \
        | grep -oP 'pid=\K[0-9]+' || true)
    for pid in $PIDS; do
        COMM=$(ps -p "$pid" -o comm= 2>/dev/null || echo "unknown")
        echo "→ Killing lingering process on port $port: $COMM (pid $pid)"
        kill -9 "$pid" 2>/dev/null || true
    done
done

# Also kill any uvicorn/next processes that mention heimdall in their args
for pattern in "uvicorn main:app" "next start"; do
    PIDS=$(pgrep -f "$pattern" 2>/dev/null || true)
    for pid in $PIDS; do
        COMM=$(ps -p "$pid" -o args= 2>/dev/null || echo "")
        if echo "$COMM" | grep -qi "heimdall\|$INSTALL_DIR"; then
            echo "→ Killing lingering process: $COMM (pid $pid)"
            kill -9 "$pid" 2>/dev/null || true
        fi
    done
done

# ── Remove CLI, sudoers rule, and desktop entry ───────────────────────────────

if [[ -f /usr/local/bin/heimdall ]]; then
    rm -f /usr/local/bin/heimdall
    echo "✓ heimdall CLI removed"
fi

if [[ -f /etc/sudoers.d/heimdall ]]; then
    rm -f /etc/sudoers.d/heimdall
    echo "✓ Sudoers rule removed"
fi

if [[ -f /usr/share/applications/heimdall.desktop ]]; then
    rm -f /usr/share/applications/heimdall.desktop
    echo "✓ Desktop entry removed"
fi

# ── Purge ─────────────────────────────────────────────────────────────────────

if [[ "$PURGE" == "true" ]]; then
    echo ""
    echo "→ Purging runtime data and build artifacts..."

    _rm() {
        if [[ -e "$1" ]]; then
            rm -rf "$1"
            echo "✓ Removed: $1"
        fi
    }

    _rm "$INSTALL_DIR/backend/.venv"
    _rm "$INSTALL_DIR/frontend/.next"
    _rm "$INSTALL_DIR/frontend/node_modules"
    _rm "$INSTALL_DIR/.env"
    _rm "$INSTALL_DIR/data"
    _rm "$INSTALL_DIR/config"
    _rm "$INSTALL_DIR/tasks"
    _rm "$INSTALL_DIR/workspace"

    # Clear systemd journal logs for heimdall units
    journalctl --rotate 2>/dev/null || true
    journalctl --vacuum-time=1s --unit=heimdall-backend  2>/dev/null || true
    journalctl --vacuum-time=1s --unit=heimdall-frontend 2>/dev/null || true
    echo "✓ Journal logs cleared"

    # If installed at the canonical get-heimdall.sh location, remove the repo too
    if [[ "$INSTALL_DIR" == "/opt/heimdall" ]]; then
        echo ""
        echo "→ Removing /opt/heimdall (canonical install location)..."
        cd /
        rm -rf /opt/heimdall
        echo "✓ /opt/heimdall removed"
    else
        echo ""
        echo "→ Install directory $INSTALL_DIR was not /opt/heimdall — leaving repo in place."
        echo "  Delete manually if needed:  rm -rf $INSTALL_DIR"
    fi
else
    echo ""
    echo "→ Runtime data kept (.env, data/, config/, tasks/, workspace/)."
    echo "  Re-run with --purge to delete everything."
fi

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "=== Heimdall uninstalled ==="
