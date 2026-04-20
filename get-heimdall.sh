#!/usr/bin/env bash
# Heimdall AI Automation — Bootstrap installer
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Chrisl154/heimdall-ai-automation/master/get-heimdall.sh | sudo bash
#   curl -fsSL https://raw.githubusercontent.com/Chrisl154/heimdall-ai-automation/master/get-heimdall.sh | sudo bash -s -- --host 192.168.1.50
#   curl -fsSL https://raw.githubusercontent.com/Chrisl154/heimdall-ai-automation/master/get-heimdall.sh | sudo bash -s -- --uninstall
#   curl -fsSL https://raw.githubusercontent.com/Chrisl154/heimdall-ai-automation/master/get-heimdall.sh | sudo bash -s -- --uninstall --purge
set -e

REPO_URL="https://github.com/Chrisl154/heimdall-ai-automation.git"
INSTALL_DIR="/opt/heimdall"
BRANCH="master"

# ── Parse args ────────────────────────────────────────────────────────────────
UNINSTALL=false
PURGE=false
FORWARD_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --uninstall) UNINSTALL=true; shift ;;
        --purge)     PURGE=true; shift ;;
        --dir)       INSTALL_DIR="$2"; shift 2 ;;
        *)           FORWARD_ARGS+=("$1"); shift ;;
    esac
done

# ── Uninstall path ────────────────────────────────────────────────────────────
if [[ "$UNINSTALL" == "true" ]]; then
    if [[ ! -f "$INSTALL_DIR/uninstall.sh" ]]; then
        echo "✗ Heimdall not found at $INSTALL_DIR"
        exit 1
    fi
    echo "=== Heimdall Uninstaller ==="
    if [[ "$PURGE" == "true" ]]; then
        bash "$INSTALL_DIR/uninstall.sh" --purge
    else
        bash "$INSTALL_DIR/uninstall.sh"
    fi
    exit 0
fi

# ── Install path ──────────────────────────────────────────────────────────────
echo "=== Heimdall Bootstrap ==="

# Check git
if ! command -v git &>/dev/null; then
    echo "✗ git is required. Install it first: apt install git / yum install git"
    exit 1
fi

# Check for existing install
if [[ -d "$INSTALL_DIR/.git" ]]; then
    echo "→ Existing install found at $INSTALL_DIR — pulling latest..."
    git -C "$INSTALL_DIR" pull --ff-only
else
    echo "→ Cloning to $INSTALL_DIR..."
    git clone "$REPO_URL" "$INSTALL_DIR" --branch "$BRANCH" --depth 1
fi

APP_DIR="$INSTALL_DIR"

if [[ ! -f "$APP_DIR/install.sh" ]]; then
    echo "✗ install.sh not found in $APP_DIR — repo structure may have changed."
    exit 1
fi

echo "→ Running installer..."
bash "$APP_DIR/install.sh" "${FORWARD_ARGS[@]}"
