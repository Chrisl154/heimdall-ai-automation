#!/usr/bin/env bash
# Heimdall AI Automation — Linux installer
# Usage: sudo bash install.sh [--host <hostname-or-ip>] [--backend-port <port>] [--frontend-port <port>]
#
# --host            Public hostname or IP users will use to reach this server.
#                   Defaults to the machine's primary LAN IP (auto-detected).
#                   Set to a domain name when behind a reverse proxy.
# --backend-port    Port the FastAPI backend listens on. Default: 8000
# --frontend-port   Port the Next.js frontend listens on. Default: 3000
set -e

# ── Argument parsing ──────────────────────────────────────────────────────────

PUBLIC_HOST=""
BACKEND_PORT="8000"
FRONTEND_PORT="3000"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)           PUBLIC_HOST="$2";    shift 2 ;;
        --backend-port)   BACKEND_PORT="$2";   shift 2 ;;
        --frontend-port)  FRONTEND_PORT="$2";  shift 2 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

# Auto-detect LAN IP if --host not supplied
if [[ -z "$PUBLIC_HOST" ]]; then
    PUBLIC_HOST=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}' | head -1)
    PUBLIC_HOST="${PUBLIC_HOST:-localhost}"
fi

echo "=== Heimdall Installer ==="
echo "→ Public host:     $PUBLIC_HOST"
echo "→ Backend port:    $BACKEND_PORT"
echo "→ Frontend port:   $FRONTEND_PORT"
echo ""

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
# NEXT_PUBLIC_API_URL must be set at build time — it gets baked into the JS bundle.
# We point it at the server's real public address so browser API calls work remotely.

cd "$INSTALL_DIR/frontend"
npm install --silent
NEXT_PUBLIC_API_URL="http://${PUBLIC_HOST}:${BACKEND_PORT}" npm run build
echo "✓ Frontend built (API URL: http://${PUBLIC_HOST}:${BACKEND_PORT})"
cd "$INSTALL_DIR"

# ── Environment ───────────────────────────────────────────────────────────────

if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
    # Patch CORS to allow requests from the frontend's real origin
    sed -i "s|^HEIMDALL_HOST=.*|HEIMDALL_HOST=0.0.0.0|" "$INSTALL_DIR/.env"
    sed -i "s|^HEIMDALL_PORT=.*|HEIMDALL_PORT=${BACKEND_PORT}|" "$INSTALL_DIR/.env"
    echo "CORS_ORIGINS=http://${PUBLIC_HOST}:${FRONTEND_PORT},http://localhost:${FRONTEND_PORT}" >> "$INSTALL_DIR/.env"
    echo "→ Created .env (CORS set for http://${PUBLIC_HOST}:${FRONTEND_PORT})"
else
    # .env exists — make sure CORS includes the new host if not already present
    if ! grep -q "$PUBLIC_HOST" "$INSTALL_DIR/.env"; then
        echo "" >> "$INSTALL_DIR/.env"
        echo "CORS_ORIGINS=http://${PUBLIC_HOST}:${FRONTEND_PORT},http://localhost:${FRONTEND_PORT}" >> "$INSTALL_DIR/.env"
        echo "→ Appended CORS_ORIGINS to existing .env"
    else
        echo "→ .env already exists and includes $PUBLIC_HOST"
    fi
fi

# ── Systemd — backend ─────────────────────────────────────────────────────────

cat > /etc/systemd/system/heimdall-backend.service <<EOF
[Unit]
Description=Heimdall AI Automation — Backend
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
echo "✓ Backend service installed (heimdall-backend)"

# ── Systemd — frontend ────────────────────────────────────────────────────────

cat > /etc/systemd/system/heimdall-frontend.service <<EOF
[Unit]
Description=Heimdall AI Automation — Frontend
After=network.target heimdall-backend.service

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR/frontend
# PORT env var tells Next.js which port to bind
Environment=PORT=${FRONTEND_PORT}
ExecStart=$(which node) $INSTALL_DIR/frontend/node_modules/.bin/next start -p ${FRONTEND_PORT}
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
echo "✓ Frontend service installed (heimdall-frontend)"

systemctl daemon-reload
systemctl enable heimdall-backend heimdall-frontend
echo "✓ Both services enabled (start on boot)"

# ── heimdall CLI ──────────────────────────────────────────────────────────────

cat > /usr/local/bin/heimdall <<HEIMDALL_CLI
#!/usr/bin/env bash
case "\$1" in
  start)
    systemctl start heimdall-backend heimdall-frontend
    echo "Heimdall started — http://${PUBLIC_HOST}:${FRONTEND_PORT}" ;;
  stop)
    systemctl stop heimdall-frontend heimdall-backend
    echo "Heimdall stopped." ;;
  restart)
    systemctl restart heimdall-backend heimdall-frontend
    echo "Heimdall restarted." ;;
  status)
    echo "=== Backend ===" && systemctl status heimdall-backend --no-pager
    echo "" && echo "=== Frontend ===" && systemctl status heimdall-frontend --no-pager ;;
  logs)
    journalctl -u heimdall-backend -u heimdall-frontend -f ;;
  logs-backend)
    journalctl -u heimdall-backend -f ;;
  logs-frontend)
    journalctl -u heimdall-frontend -f ;;
  open)
    xdg-open "http://${PUBLIC_HOST}:${FRONTEND_PORT}" 2>/dev/null \
      || echo "Open http://${PUBLIC_HOST}:${FRONTEND_PORT} in your browser" ;;
  *)
    echo "Usage: heimdall {start|stop|restart|status|logs|logs-backend|logs-frontend|open}"
    exit 1 ;;
esac
HEIMDALL_CLI
chmod +x /usr/local/bin/heimdall
echo "✓ Management CLI installed (/usr/local/bin/heimdall)"

# ── Desktop entry ─────────────────────────────────────────────────────────────

if [[ -d /usr/share/applications ]]; then
    cat > /usr/share/applications/heimdall.desktop <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Heimdall AI Automation
Comment=Multi-AI orchestration platform
Exec=xdg-open http://${PUBLIC_HOST}:${FRONTEND_PORT}
Icon=$INSTALL_DIR/frontend/public/favicon.ico
Categories=Development;
StartupNotify=false
EOF
    echo "✓ Desktop entry installed"
fi

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "=== Heimdall installed ==="
echo ""
echo "Next steps:"
echo "  1. heimdall start"
echo "  2. Open http://${PUBLIC_HOST}:${FRONTEND_PORT}"
echo "     — Setup wizard runs automatically on first visit"
echo ""
echo "Or pre-configure .env before starting:"
echo "  Edit $INSTALL_DIR/.env"
echo "  — Set HEIMDALL_VAULT_KEY  (generate: python3 -c \"import base64,os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())\")"
echo "  — Set HEIMDALL_API_TOKEN  (generate: openssl rand -hex 32)"
echo "  Then: heimdall start"
