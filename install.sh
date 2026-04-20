#!/usr/bin/env bash
# Heimdall AI Automation — Linux installer
# Usage: sudo bash install.sh [--host <hostname-or-ip>] [--backend-port <port>] [--frontend-port <port>]
#
# --host            Public hostname or IP users will reach this server at.
#                   Defaults to the machine's primary LAN IP (auto-detected).
# --backend-port    FastAPI backend port. Default: 8000
# --frontend-port   Next.js frontend port. Default: 3000
set -euo pipefail

# ── Root check ────────────────────────────────────────────────────────────────

if [[ $EUID -ne 0 ]]; then
    echo "✗ This installer must be run as root:  sudo bash install.sh"
    exit 1
fi

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
    PUBLIC_HOST=$(ip route get 1.1.1.1 2>/dev/null \
        | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1)}' | head -1)
    PUBLIC_HOST="${PUBLIC_HOST:-localhost}"
fi

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Heimdall Installer ==="
echo "→ Install directory: $INSTALL_DIR"
echo "→ Public host:       $PUBLIC_HOST"
echo "→ Backend port:      $BACKEND_PORT"
echo "→ Frontend port:     $FRONTEND_PORT"
echo ""

# ── Package manager detection ─────────────────────────────────────────────────

PKG_MGR=""
if   command -v apt-get &>/dev/null; then PKG_MGR="apt"
elif command -v dnf     &>/dev/null; then PKG_MGR="dnf"
elif command -v yum     &>/dev/null; then PKG_MGR="yum"
elif command -v pacman  &>/dev/null; then PKG_MGR="pacman"
elif command -v apk     &>/dev/null; then PKG_MGR="apk"
else
    echo "✗ No supported package manager found (apt / dnf / yum / pacman / apk)"
    exit 1
fi
echo "→ Package manager: $PKG_MGR"

# ── System dependencies ───────────────────────────────────────────────────────

echo "→ Installing system dependencies..."
case "$PKG_MGR" in
    apt)
        export DEBIAN_FRONTEND=noninteractive
        apt-get update -qq
        apt-get install -y -qq \
            git curl ca-certificates gnupg lsb-release \
            build-essential libssl-dev libffi-dev \
            python3 python3-pip python3-venv python3-dev
        ;;
    dnf)
        dnf install -y -q \
            git curl ca-certificates gnupg \
            gcc gcc-c++ make openssl-devel libffi-devel \
            python3 python3-pip python3-devel
        ;;
    yum)
        yum install -y -q \
            git curl ca-certificates gnupg \
            gcc gcc-c++ make openssl-devel libffi-devel \
            python3 python3-pip python3-devel
        ;;
    pacman)
        pacman -Sy --noconfirm \
            git curl ca-certificates gnupg \
            base-devel openssl \
            python python-pip
        ;;
    apk)
        apk add --no-cache \
            git curl ca-certificates gnupg \
            build-base openssl-dev libffi-dev \
            python3 py3-pip python3-dev
        ;;
esac
echo "✓ System dependencies installed"

# ── Python 3.10+ ─────────────────────────────────────────────────────────────
# All dependencies support Python 3.10+. Ubuntu 22.04 ships 3.10 natively —
# no PPA needed. Only attempt to install if the system has nothing usable.

PYTHON_BIN="python3"
_pyver() { "$1" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0"; }
_pyok()  { local v; v=$(_pyver "$1"); local maj min; maj=${v%%.*}; min=${v##*.}
           [[ "$maj" -gt 3 ]] || { [[ "$maj" -eq 3 ]] && [[ "$min" -ge 10 ]]; }; }

# Prefer the highest available version already on the system
for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" &>/dev/null && _pyok "$candidate"; then
        PYTHON_BIN="$candidate"
        break
    fi
done

if ! _pyok "$PYTHON_BIN"; then
    CURRENT_VER=$(_pyver "$PYTHON_BIN")
    echo "→ Python $CURRENT_VER found — need 3.10+, attempting install..."
    case "$PKG_MGR" in
        apt)
            apt-get install -y -qq python3 python3-venv python3-dev || {
                echo "✗ Could not install Python 3.10+. Install manually and re-run."
                exit 1
            }
            PYTHON_BIN="python3"
            ;;
        dnf)
            dnf install -y python3 python3-devel || {
                echo "✗ Could not install Python 3.10+ via dnf. Install manually and re-run."
                exit 1
            }
            ;;
        yum)
            yum install -y python3 python3-devel || {
                echo "✗ Could not install Python 3.10+ via yum. Install manually and re-run."
                exit 1
            }
            ;;
        *)
            echo "✗ Python 3.10+ required (found $CURRENT_VER). Install manually and re-run."
            exit 1
            ;;
    esac
fi

PYTHON_VERSION=$(_pyver "$PYTHON_BIN")
echo "✓ Python $PYTHON_VERSION ($PYTHON_BIN)"

# Ensure venv module is present for the selected Python
if ! "$PYTHON_BIN" -m venv --help &>/dev/null; then
    VER=$(_pyver "$PYTHON_BIN")
    case "$PKG_MGR" in
        apt) apt-get install -y -qq "python${VER}-venv" ;;
        *)
            echo "✗ python venv module missing for $PYTHON_BIN. Install python${VER}-venv manually."
            exit 1
            ;;
    esac
fi

# ── Node.js 18+ ───────────────────────────────────────────────────────────────

NODE_MAJ=$(node -v 2>/dev/null | sed 's/v//' | cut -d. -f1 || echo "0")

if [[ "$NODE_MAJ" -lt 18 ]]; then
    echo "→ Node.js ${NODE_MAJ:-not found} — installing Node.js 22 LTS..."
    case "$PKG_MGR" in
        apt)
            curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
            apt-get install -y -qq nodejs
            ;;
        dnf)
            curl -fsSL https://rpm.nodesource.com/setup_22.x | bash -
            dnf install -y nodejs
            ;;
        yum)
            curl -fsSL https://rpm.nodesource.com/setup_22.x | bash -
            yum install -y nodejs
            ;;
        pacman)
            pacman -Sy --noconfirm nodejs npm
            ;;
        apk)
            apk add --no-cache nodejs npm
            ;;
        *)
            echo "✗ Cannot auto-install Node.js. Install Node.js 18+ manually and re-run."
            exit 1
            ;;
    esac
fi

NODE_MAJ=$(node -v 2>/dev/null | sed 's/v//' | cut -d. -f1 || echo "0")
if [[ "$NODE_MAJ" -lt 18 ]]; then
    echo "✗ Node.js 18+ required but install failed. Install manually and re-run."
    exit 1
fi
echo "✓ Node.js $(node -v)"

# ── Port availability ─────────────────────────────────────────────────────────

for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
    if ss -tlnp 2>/dev/null | grep -q ":${port} "; then
        echo "⚠  Port $port is already in use — pass --backend-port / --frontend-port to override."
    fi
done

# ── Backend virtualenv ────────────────────────────────────────────────────────

echo "→ Setting up backend virtualenv..."
VENV_DIR="$INSTALL_DIR/backend/.venv"
if [[ ! -d "$VENV_DIR" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

PIP="$VENV_DIR/bin/pip"
"$PIP" install --upgrade pip --quiet

echo "→ Installing Python dependencies (this may take a minute)..."
"$PIP" install -r "$INSTALL_DIR/backend/requirements.txt" \
    || { echo "✗ Backend dependency install failed — see output above."; exit 1; }
echo "✓ Backend dependencies installed"

# ── Frontend build ────────────────────────────────────────────────────────────

echo "→ Installing frontend packages..."
cd "$INSTALL_DIR/frontend"
npm install \
    || { echo "✗ npm install failed — see output above."; exit 1; }

echo "→ Building frontend (may take a few minutes)..."
NEXT_PUBLIC_API_URL="http://${PUBLIC_HOST}:${BACKEND_PORT}" npm run build \
    || { echo "✗ Frontend build failed — see output above."; exit 1; }

echo "✓ Frontend built  (API: http://${PUBLIC_HOST}:${BACKEND_PORT})"
cd "$INSTALL_DIR"

# ── Environment file ──────────────────────────────────────────────────────────

if [[ ! -f "$INSTALL_DIR/.env.example" ]]; then
    echo "✗ .env.example missing from $INSTALL_DIR — repo may be incomplete."
    exit 1
fi

_gen_fernet() {
    "$VENV_DIR/bin/python" -c \
        "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
}

if [[ ! -f "$INSTALL_DIR/.env" ]]; then
    cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"

    VAULT_KEY=$(_gen_fernet)
    SECRET_KEY=$(openssl rand -hex 32)
    API_TOKEN=$(openssl rand -hex 32)

    sed -i "s|^HEIMDALL_VAULT_KEY=.*|HEIMDALL_VAULT_KEY=${VAULT_KEY}|"     "$INSTALL_DIR/.env"
    sed -i "s|^HEIMDALL_SECRET_KEY=.*|HEIMDALL_SECRET_KEY=${SECRET_KEY}|"  "$INSTALL_DIR/.env"
    sed -i "s|^HEIMDALL_API_TOKEN=.*|HEIMDALL_API_TOKEN=${API_TOKEN}|"     "$INSTALL_DIR/.env"
    sed -i "s|^HEIMDALL_HOST=.*|HEIMDALL_HOST=0.0.0.0|"                    "$INSTALL_DIR/.env"
    sed -i "s|^HEIMDALL_PORT=.*|HEIMDALL_PORT=${BACKEND_PORT}|"            "$INSTALL_DIR/.env"
    echo "CORS_ORIGINS=http://${PUBLIC_HOST}:${FRONTEND_PORT},http://localhost:${FRONTEND_PORT}" \
        >> "$INSTALL_DIR/.env"
    echo "✓ .env created — vault key, secret key, and API token auto-generated"
else
    # Fix placeholder vault key if still present
    if grep -q "<generate-with-fernet>" "$INSTALL_DIR/.env"; then
        VAULT_KEY=$(_gen_fernet)
        sed -i "s|^HEIMDALL_VAULT_KEY=.*|HEIMDALL_VAULT_KEY=${VAULT_KEY}|" "$INSTALL_DIR/.env"
        echo "→ Auto-generated HEIMDALL_VAULT_KEY in existing .env"
    fi
    # Append CORS if public host not present
    if ! grep -q "CORS_ORIGINS" "$INSTALL_DIR/.env"; then
        echo "CORS_ORIGINS=http://${PUBLIC_HOST}:${FRONTEND_PORT},http://localhost:${FRONTEND_PORT}" \
            >> "$INSTALL_DIR/.env"
        echo "→ Added CORS_ORIGINS to existing .env"
    elif ! grep -q "$PUBLIC_HOST" "$INSTALL_DIR/.env"; then
        echo "CORS_ORIGINS=http://${PUBLIC_HOST}:${FRONTEND_PORT},http://localhost:${FRONTEND_PORT}" \
            >> "$INSTALL_DIR/.env"
        echo "→ Appended CORS_ORIGINS for $PUBLIC_HOST to existing .env"
    else
        echo "→ .env already configured for $PUBLIC_HOST"
    fi
fi

# ── Systemd — backend ─────────────────────────────────────────────────────────
# Run uvicorn directly (no reload) with PYTHONPATH pointing at the backend dir
# so `import main`, `import core`, `import scheduler` all resolve correctly,
# while WorkingDirectory stays at the project root so relative data/ paths work.

UVICORN_BIN="$VENV_DIR/bin/uvicorn"

cat > /etc/systemd/system/heimdall-backend.service <<EOF
[Unit]
Description=Heimdall AI Automation — Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONPATH=$INSTALL_DIR/backend
ExecStart=$UVICORN_BIN main:app --host 0.0.0.0 --port ${BACKEND_PORT} --workers 1
Restart=on-failure
RestartSec=5
EnvironmentFile=$INSTALL_DIR/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF
echo "✓ Backend service installed  (heimdall-backend)"

# ── Systemd — frontend ────────────────────────────────────────────────────────

NODE_BIN=$(which node)

cat > /etc/systemd/system/heimdall-frontend.service <<EOF
[Unit]
Description=Heimdall AI Automation — Frontend
After=network.target heimdall-backend.service

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR/frontend
Environment=PORT=${FRONTEND_PORT}
ExecStart=$NODE_BIN $INSTALL_DIR/frontend/node_modules/.bin/next start -p ${FRONTEND_PORT}
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
echo "✓ heimdall CLI installed (/usr/local/bin/heimdall)"

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

# ── Start services ────────────────────────────────────────────────────────────

echo ""
echo "→ Starting services..."
systemctl start heimdall-backend heimdall-frontend
sleep 3

BACKEND_UP=false
FRONTEND_UP=false
systemctl is-active --quiet heimdall-backend  && BACKEND_UP=true
systemctl is-active --quiet heimdall-frontend && FRONTEND_UP=true

if $BACKEND_UP && $FRONTEND_UP; then
    echo "✓ Both services running"
else
    $BACKEND_UP  || echo "⚠  heimdall-backend  failed to start — check: journalctl -u heimdall-backend"
    $FRONTEND_UP || echo "⚠  heimdall-frontend failed to start — check: journalctl -u heimdall-frontend"
fi

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║       Heimdall installed successfully!           ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Dashboard:  http://${PUBLIC_HOST}:${FRONTEND_PORT}"
echo "  API docs:   http://${PUBLIC_HOST}:${BACKEND_PORT}/docs"
echo ""
echo "  heimdall start    — start services"
echo "  heimdall stop     — stop services"
echo "  heimdall restart  — restart services"
echo "  heimdall status   — check health"
echo "  heimdall logs     — follow logs"
echo ""
echo "  Setup wizard runs automatically on first visit."
echo ""

if command -v ufw &>/dev/null; then
    UFW_STATUS=$(ufw status 2>/dev/null | head -1)
    if [[ "$UFW_STATUS" == *"active"* ]]; then
        echo "  ufw is active — open ports if accessing remotely:"
        echo "    sudo ufw allow ${BACKEND_PORT}/tcp"
        echo "    sudo ufw allow ${FRONTEND_PORT}/tcp"
        echo ""
    fi
fi
