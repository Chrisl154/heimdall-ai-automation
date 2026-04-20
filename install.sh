#!/usr/bin/env bash
# Heimdall AI Automation — Linux installer
# Usage: sudo bash install.sh [--host <hostname-or-ip>] [--port <port>]
#
# --host   Public hostname or IP users will reach this server at.
#          Defaults to the machine's primary LAN IP (auto-detected).
# --port   Port the FastAPI backend (and frontend) listens on. Default: 8000
#
# Architecture: Next.js is built as a static export (out/) and served directly
# by the FastAPI backend. Only ONE service and ONE port needed.
set -euo pipefail

# ── Root check ────────────────────────────────────────────────────────────────

if [[ $EUID -ne 0 ]]; then
    echo "✗ This installer must be run as root:  sudo bash install.sh"
    exit 1
fi

# ── Argument parsing ──────────────────────────────────────────────────────────

PUBLIC_HOST=""
PORT="8000"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)           PUBLIC_HOST="$2"; shift 2 ;;
        --port)           PORT="$2";        shift 2 ;;
        # Legacy flags — accepted but ignored
        --backend-port)   PORT="$2";        shift 2 ;;
        --frontend-port)  shift 2 ;;
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
echo "→ Port:              $PORT"
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

PYTHON_BIN="python3"
_pyver() { "$1" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0"; }
_pyok()  { local v; v=$(_pyver "$1"); local maj min; maj=${v%%.*}; min=${v##*.}
           [[ "$maj" -gt 3 ]] || { [[ "$maj" -eq 3 ]] && [[ "$min" -ge 10 ]]; }; }

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
        dnf) dnf install -y python3 python3-devel || { echo "✗ Could not install Python 3.10+."; exit 1; } ;;
        yum) yum install -y python3 python3-devel || { echo "✗ Could not install Python 3.10+."; exit 1; } ;;
        *)
            echo "✗ Python 3.10+ required (found $CURRENT_VER). Install manually and re-run."
            exit 1
            ;;
    esac
fi

PYTHON_VERSION=$(_pyver "$PYTHON_BIN")
echo "✓ Python $PYTHON_VERSION ($PYTHON_BIN)"

if ! "$PYTHON_BIN" -m venv --help &>/dev/null; then
    VER=$(_pyver "$PYTHON_BIN")
    case "$PKG_MGR" in
        apt) apt-get install -y -qq "python${VER}-venv" ;;
        *) echo "✗ python venv module missing. Install python${VER}-venv manually." && exit 1 ;;
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
        pacman) pacman -Sy --noconfirm nodejs npm ;;
        apk)    apk add --no-cache nodejs npm ;;
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

if ss -tlnp 2>/dev/null | grep -q ":${PORT} "; then
    echo "⚠  Port $PORT is already in use — pass --port to use a different port."
fi

# ── Stop any existing services before rebuilding ──────────────────────────────

for svc in heimdall-backend heimdall-frontend; do
    if systemctl is-active --quiet "$svc" 2>/dev/null; then
        systemctl stop "$svc" 2>/dev/null || true
        echo "→ Stopped existing $svc"
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

# ── Frontend static build ─────────────────────────────────────────────────────
# next.config.js uses output:"export" — builds a static site into out/.
# The FastAPI backend serves this out/ directory directly (see main.py).
# No separate frontend service is needed.

echo "→ Installing frontend packages..."
cd "$INSTALL_DIR/frontend"
npm install \
    || { echo "✗ npm install failed — see output above."; exit 1; }

echo "→ Building frontend static export (may take a few minutes)..."
npm run build \
    || { echo "✗ Frontend build failed — see output above."; exit 1; }

if [[ ! -d "$INSTALL_DIR/frontend/out" ]]; then
    echo "✗ Frontend build did not produce an out/ directory."
    exit 1
fi
echo "✓ Frontend built → out/  (API: http://${PUBLIC_HOST}:${PORT})"
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
    sed -i "s|^HEIMDALL_PORT=.*|HEIMDALL_PORT=${PORT}|"                    "$INSTALL_DIR/.env"
    echo "CORS_ORIGINS=http://${PUBLIC_HOST}:${PORT},http://localhost:${PORT}" \
        >> "$INSTALL_DIR/.env"
    echo "✓ .env created — vault key, secret key, and API token auto-generated"
else
    if grep -q "<generate-with-fernet>" "$INSTALL_DIR/.env"; then
        VAULT_KEY=$(_gen_fernet)
        sed -i "s|^HEIMDALL_VAULT_KEY=.*|HEIMDALL_VAULT_KEY=${VAULT_KEY}|" "$INSTALL_DIR/.env"
        echo "→ Auto-generated HEIMDALL_VAULT_KEY in existing .env"
    fi
    sed -i "s|^HEIMDALL_PORT=.*|HEIMDALL_PORT=${PORT}|" "$INSTALL_DIR/.env" 2>/dev/null || true
    if ! grep -q "CORS_ORIGINS" "$INSTALL_DIR/.env"; then
        echo "CORS_ORIGINS=http://${PUBLIC_HOST}:${PORT},http://localhost:${PORT}" \
            >> "$INSTALL_DIR/.env"
        echo "→ Added CORS_ORIGINS to existing .env"
    fi
    echo "→ .env already exists — kept"
fi

# Read final token for display at end (works for both new and existing .env)
API_TOKEN=$(grep "^HEIMDALL_API_TOKEN=" "$INSTALL_DIR/.env" | cut -d= -f2)

# ── Disable and remove legacy frontend service if present ────────────────────

if [[ -f /etc/systemd/system/heimdall-frontend.service ]]; then
    systemctl stop    heimdall-frontend 2>/dev/null || true
    systemctl disable heimdall-frontend 2>/dev/null || true
    rm -f /etc/systemd/system/heimdall-frontend.service
    echo "→ Removed legacy heimdall-frontend service (no longer needed)"
fi

# ── Systemd — backend (serves API + static frontend) ─────────────────────────

UVICORN_BIN="$VENV_DIR/bin/uvicorn"

cat > /etc/systemd/system/heimdall-backend.service <<EOF
[Unit]
Description=Heimdall AI Automation
After=network.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONPATH=$INSTALL_DIR/backend
ExecStart=$UVICORN_BIN main:app --host 0.0.0.0 --port ${PORT} --workers 1
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
echo "✓ heimdall-backend service installed and enabled"

# ── Sudoers rule — passwordless systemctl for heimdall ───────────────────────

SYSTEMCTL_BIN=$(which systemctl)
JOURNALCTL_BIN=$(which journalctl)
cat > /etc/sudoers.d/heimdall <<EOF
# Allow any user to manage Heimdall without a password prompt
ALL ALL=(ALL) NOPASSWD: ${SYSTEMCTL_BIN} start heimdall-backend
ALL ALL=(ALL) NOPASSWD: ${SYSTEMCTL_BIN} stop heimdall-backend
ALL ALL=(ALL) NOPASSWD: ${SYSTEMCTL_BIN} restart heimdall-backend
ALL ALL=(ALL) NOPASSWD: ${SYSTEMCTL_BIN} status heimdall-backend
ALL ALL=(ALL) NOPASSWD: ${JOURNALCTL_BIN} -u heimdall-backend *
ALL ALL=(ALL) NOPASSWD: ${JOURNALCTL_BIN} -u heimdall-backend -f
EOF
chmod 0440 /etc/sudoers.d/heimdall
echo "✓ Sudoers rule installed — heimdall CLI works without password"

# ── heimdall CLI ──────────────────────────────────────────────────────────────

cat > /usr/local/bin/heimdall <<HEIMDALL_CLI
#!/usr/bin/env bash
case "\$1" in
  start)
    sudo systemctl start heimdall-backend
    echo "Heimdall started — http://${PUBLIC_HOST}:${PORT}" ;;
  stop)
    sudo systemctl stop heimdall-backend
    echo "Heimdall stopped." ;;
  restart)
    sudo systemctl restart heimdall-backend
    echo "Heimdall restarted." ;;
  status)
    sudo systemctl status heimdall-backend --no-pager ;;
  logs)
    sudo journalctl -u heimdall-backend -f ;;
  open)
    xdg-open "http://${PUBLIC_HOST}:${PORT}" 2>/dev/null \
      || echo "Open http://${PUBLIC_HOST}:${PORT} in your browser" ;;
  update)
    bash "${INSTALL_DIR}/update.sh" "\${@:2}" ;;
  uninstall)
    echo "This will remove Heimdall services and CLI."
    echo "Your vault, API keys, GitHub token, and config will be PRESERVED."
    echo "Use 'heimdall uninstall --purge' to delete everything."
    echo ""
    read -rp "Continue? [y/N] " confirm
    [[ "\$confirm" =~ ^[Yy]$ ]] || { echo "Cancelled."; exit 0; }
    sudo bash "${INSTALL_DIR}/uninstall.sh" "\${@:2}" ;;
  *)
    echo "Usage: heimdall {start|stop|restart|status|logs|open|update|uninstall}"
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
Exec=xdg-open http://${PUBLIC_HOST}:${PORT}
Icon=$INSTALL_DIR/frontend/public/favicon.ico
Categories=Development;
StartupNotify=false
EOF
    echo "✓ Desktop entry installed"
fi

# ── Start service ─────────────────────────────────────────────────────────────

echo ""
echo "→ Starting Heimdall..."
systemctl start heimdall-backend
sleep 3

if systemctl is-active --quiet heimdall-backend; then
    echo "✓ Heimdall is running"
else
    echo "⚠  heimdall-backend failed to start — check: journalctl -u heimdall-backend"
fi

# ── Done ──────────────────────────────────────────────────────────────────────

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║       Heimdall installed successfully!           ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Open:     http://${PUBLIC_HOST}:${PORT}"
echo "  API docs: http://${PUBLIC_HOST}:${PORT}/docs"
echo ""
echo "  API Token (copy this — needed for first login):"
echo "  ${API_TOKEN}"
echo ""
echo "  heimdall start     — start"
echo "  heimdall stop      — stop"
echo "  heimdall restart   — restart"
echo "  heimdall status    — check health"
echo "  heimdall logs      — follow logs"
echo "  heimdall update    — pull latest + rebuild + restart"
echo "  heimdall uninstall — remove Heimdall (keeps vault & config)"
echo ""
echo "  Setup wizard runs automatically on first visit."
echo "  Token is also saved in: $INSTALL_DIR/.env"
echo ""

if command -v ufw &>/dev/null; then
    if ufw status 2>/dev/null | grep -q "active"; then
        echo "  ufw is active — open port if accessing remotely:"
        echo "    sudo ufw allow ${PORT}/tcp"
        echo ""
    fi
fi
