#!/usr/bin/env bash
# Heimdall AI Automation — Linux installer
# Usage: sudo bash install.sh
set -e

echo "=== Heimdall Installer ==="

# ── Prerequisites ─────────────────────────────────────────────────────────────

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [[ "$PYTHON_MAJOR" -lt 3 ]] || { [[ "$PYTHON_MAJOR" -eq 3 ]] && [[ "$PYTHON_MINOR" -lt 11 ]]; }; then
    echo "✗ Python 3.11+ required (found $PYTHON_VERSION)" && exit 1
fi
echo "✓ Python $PYTHON_VERSION"

NODE_VERSION=$(node -v 2>/dev/null | cut -d. -f1 | tr -d 'v')
if [[ -z "$NODE_VERSION" ]] || [[ "$NODE_VERSION" -lt 18 ]]; then
    echo "✗ Node.js 18+ required (found ${NODE_VERSION:-none})" && exit 1
fi
echo "✓ Node.js $NODE_VERSION"

# ── Paths ─────────────────────────────────────────────────────────────────────

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "→ Install directory: $INSTALL_DIR"

# ── Backend virtualenv ────────────────────────────────────────────────────────

if [[ ! -d "$INSTALL_DIR/backend/.venv" ]]; then
    echo "Creating backend virtualenv..."
    python3 -m venv "$INSTALL_DIR/backend/.venv"
fi
source "$INSTALL_DIR/backend/.venv/bin/activate"
pip install --quiet -r "$INSTALL_DIR/backend/requirements.txt"
echo "✓ Backend dependencies installed"

# ── Frontend build ────────────────────────────────────────────────────────────

cd "$INSTALL_DIR/frontend"
npm install --silent
npm run build
echo "✓ Frontend built"
cd "$INSTALL_DIR"

# ── Environment ───────────────────────────────────────────────────────────────

if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    echo "→ Created .env from .env.example — edit it before starting"
else
    echo "→ .env already exists, skipping"
fi

# ── Systemd service ───────────────────────────────────────────────────────────

cat > /etc/systemd/system/heimdall-backend.service <<EOF
[Unit]
Description=Heimdall AI Automation Backend
After=network.target

[Service]
Type=simple
# Run from project root so config/, data/, tasks/ resolve correctly
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/backend/.venv/bin/python $INSTALL_DIR/backend/main.py
Restart=on-failure
RestartSec=5
EnvironmentFile=$INSTALL_DIR/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable heimdall-backend
echo "✓ Systemd service installed (heimdall-backend)"

# ── heimdall CLI ──────────────────────────────────────────────────────────────

cat > /usr/local/bin/heimdall <<'HEIMDALL_CLI'
#!/usr/bin/env bash
case "$1" in
  start)   systemctl start   heimdall-backend && echo "Heimdall started." ;;
  stop)    systemctl stop    heimdall-backend && echo "Heimdall stopped." ;;
  restart) systemctl restart heimdall-backend && echo "Heimdall restarted." ;;
  status)  systemctl status  heimdall-backend ;;
  logs)    journalctl -u heimdall-backend -f ;;
  open)    xdg-open http://localhost:3000 2>/dev/null || echo "Open http://localhost:3000 in your browser" ;;
  *)
    echo "Usage: heimdall {start|stop|restart|status|logs|open}"
    exit 1 ;;
esac
HEIMDALL_CLI
chmod +x /usr/local/bin/heimdall
echo "✓ Management CLI installed (/usr/local/bin/heimdall)"

# ── Desktop entry ─────────────────────────────────────────────────────────────

cat > /usr/share/applications/heimdall.desktop <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Heimdall AI Automation
Comment=Multi-AI orchestration platform
Exec=xdg-open http://localhost:3000
Icon=$INSTALL_DIR/frontend/public/favicon.ico
Categories=Development;
StartupNotify=false
EOF
echo "✓ Desktop entry installed"

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "=== Heimdall installed ==="
echo ""
echo "Next steps:"
echo "  1. Edit $INSTALL_DIR/.env"
echo "     — Set HEIMDALL_VAULT_KEY (generate via setup wizard)"
echo "     — Set HEIMDALL_API_TOKEN (strong random token)"
echo "  2. heimdall start"
echo "  3. Open http://localhost:3000 — setup wizard will guide you"
echo ""
echo "Or run the setup wizard first (no .env needed):"
echo "  heimdall start"
echo "  open http://localhost:3000/setup"
