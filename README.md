# Heimdall AI Automation

A self-orchestrating multi-AI pipeline. Gemma (LM Studio) acts as the project manager, Qwen (Ollama) executes tasks, and Claude (Anthropic API) reviews and audits the output. A Next.js dashboard provides full visibility and control over the entire system.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Next.js GUI                          │
│  Chat · Tasks · Workspace · Logs · Schedule · Analytics     │
│  Settings · Git · Setup Wizard · Login                      │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼────────────────────────────────────┐
│                    FastAPI Backend                           │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │ PM (Gemma│  │  Tasks   │  │Scheduler │  │  Webhooks │  │
│  │LM Studio)│  │ Manager  │  │APScheduler  │(CRUD+fire)│  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────┘  │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │
│  │  Vault   │  │   Git    │  │Messaging │  │ Analytics │  │
│  │(Fernet)  │  │(GitPython│  │TG/Discord│  │           │  │
│  └──────────┘  └──────────┘  │/Email)   │  └───────────┘  │
│                               └──────────┘                 │
└─────────────────────────────────────────────────────────────┘
         │ Ollama            │ LM Studio       │ Anthropic
┌────────▼──────┐   ┌────────▼──────┐  ┌──────▼────────────┐
│  Qwen Worker  │   │ Gemma Orch.   │  │  Claude Reviewer  │
│ (executes)    │   │ (plans/assigns│  │  (audits output)  │
└───────────────┘   └───────────────┘  └───────────────────┘
```

| Role | Model | Host |
|---|---|---|
| Orchestrator / PM | Gemma (configurable) | LM Studio `localhost:1234` |
| Worker / Executor | Qwen3.5:35b-a3b (configurable) | Ollama `localhost:11434` |
| Reviewer / Auditor | Claude Sonnet (configurable) | Anthropic API |

---

## Install

### Linux — one-liner (curl)

```bash
# Clone and install
git clone https://github.com/Chrisl154/heimdall-ai-automation.git
cd heimdall-ai-automation/AIAutomation

# Local machine (localhost)
sudo bash install.sh

# Remote / headless server — pass your server's IP or hostname
sudo bash install.sh --host 192.168.1.50
sudo bash install.sh --host heimdall.mydomain.com

# Custom ports
sudo bash install.sh --host 192.168.1.50 --backend-port 8000 --frontend-port 3000

heimdall start
# Open http://<your-host>:3000 — setup wizard runs automatically
```

Or fetch and inspect before running:

```bash
curl -fsSL https://raw.githubusercontent.com/Chrisl154/heimdall-ai-automation/master/install.sh -o install.sh
# Review, then:
sudo bash install.sh --host <your-server-ip>
```

The installer:
- Auto-detects your LAN IP if `--host` is omitted
- Builds the frontend with `NEXT_PUBLIC_API_URL` baked in for the correct host
- Writes `CORS_ORIGINS` to `.env` so the backend accepts requests from the frontend origin
- Installs **two** systemd services: `heimdall-backend` (FastAPI) and `heimdall-frontend` (Next.js)
- Both start on boot automatically

### Uninstall

```bash
# Remove services, CLI, and desktop entry — keep .env and data
sudo bash uninstall.sh

# Remove everything including .env, vault, tasks, workspace, venv, node_modules
sudo bash uninstall.sh --purge
```

---

## Quick Start (Windows / macOS / WSL)

### Prerequisites

- Python 3.11+
- Node.js 18+
- [Ollama](https://ollama.com) running locally (worker model)
- [LM Studio](https://lmstudio.ai) running locally (orchestrator model)

### Option A — Interactive setup wizard (recommended)

```bash
# 1. Start the backend (creates venv, installs deps automatically)
bash start_backend.sh        # macOS/Linux/WSL
start_backend.bat            # Windows CMD

# 2. In a second terminal, start the frontend
bash start_frontend.sh
start_frontend.bat

# 3. Open http://localhost:3000
#    AppShell detects unconfigured state and redirects to /setup automatically.
#    Complete the 3-step wizard, restart the backend, then sign in at /login.
```

### Option B — CLI setup

```bash
python setup.py              # interactive prompts, writes .env
bash start_backend.sh
bash start_frontend.sh
```

### Option C — Docker

```bash
cp .env.example .env
# Edit .env — set HEIMDALL_VAULT_KEY and HEIMDALL_API_TOKEN
docker compose up -d
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
```

---

## First-Run Flow

1. **No `.env`** — backend starts in dev mode (auth disabled, ephemeral vault key).
2. **Browser opens** → `AppShell` detects unconfigured state → redirects to `/setup`.
3. **Setup wizard** (3 steps):
   - Step 1: Generate vault key (calls `GET /api/setup/generate-key`)
   - Step 2: Set API token (client-side random hex)
   - Step 3: Set Anthropic key + Ollama URL → `POST /api/setup/init` writes `.env`
4. **Restart backend** so `.env` is loaded.
5. **Browser** → `AppShell` detects no token in `localStorage` → redirects to `/login`.
6. **Enter token** → stored in `localStorage` → redirect to `/`.
7. All API requests include `Authorization: Bearer <token>`.

---

## Environment Variables

Copy `.env.example` to `.env` before first run (or use the setup wizard).

| Variable | Required | Default | Description |
|---|---|---|---|
| `HEIMDALL_VAULT_KEY` | **Yes** | — | Fernet key for vault encryption. Generate via setup wizard. |
| `HEIMDALL_API_TOKEN` | Recommended | `""` (auth off) | Bearer token for API. Empty = dev mode (no auth). |
| `HEIMDALL_SECRET_KEY` | Yes | placeholder | Internal signing key. Auto-generated by setup wizard. |
| `HEIMDALL_HOST` | No | `0.0.0.0` | Backend bind address. |
| `HEIMDALL_PORT` | No | `8000` | Backend port. |
| `HEIMDALL_DATA_DIR` | No | `data` | Directory for vault and schedules. |
| `HEIMDALL_CONFIG_DIR` | No | `config` | Directory for settings.yaml, restrictions.yaml, templates.yaml. |
| `HEIMDALL_TASKS_DIR` | No | `tasks` | Task backlog directory. |
| `HEIMDALL_WORKSPACE_DIR` | No | `workspace` | Agent output staging directory. |
| `OLLAMA_BASE_URL` | No | `http://127.0.0.1:11434` | Ollama endpoint. |
| `LMSTUDIO_BASE_URL` | No | `http://127.0.0.1:1234` | LM Studio endpoint. |

All other secrets (Anthropic key, GitHub token, bot tokens) go into the **vault** via Settings → AI Providers, not into `.env`.

---

## GUI Pages

| Page | Route | Description |
|---|---|---|
| Chat | `/` | Talk to the Gemma PM. Start/stop the pipeline. Live event feed via SSE. |
| Kanban | `/tasks` | View, create, update, and delete tasks. Filter by status and priority. |
| Workspace | `/workspace` | Browse agent output files. View diffs between iterations. |
| Logs | `/logs` | Live streaming event log from the pipeline. |
| Schedule | `/schedule` | Create and manage cron-based recurring tasks. Enable/disable per schedule. |
| Analytics | `/analytics` | Task completion stats, success rate, priority/tag breakdowns, recent completions. |
| Settings | `/settings` | 5-tab config panel (see below). |
| Git | `/git` | Repo status and recent commits. |
| Login | `/login` | Token entry. Stored in `localStorage`. Auto-redirected to after setup. |
| Setup | `/setup` | First-run wizard. Full-screen, no sidebar. Redirected to automatically. |

### Settings Tabs

| Tab | What it configures |
|---|---|
| AI Providers | Agent model + base URL per role (worker/reviewer/orchestrator). API key vault entries. |
| Vault | View and delete all vault keys (values never shown). |
| Channels | Telegram, Discord, and Email notification channels. |
| Webhooks | Outbound HTTP webhooks for pipeline events. CRUD + test fire. |
| Restrictions | Live YAML editor for `config/restrictions.yaml`. |

---

## API Reference

All endpoints require `Authorization: Bearer <token>` unless noted.

### Pipeline Manager
| Method | Path | Description |
|---|---|---|
| `POST` | `/api/pm/start` | Start the PM pipeline loop |
| `POST` | `/api/pm/stop` | Stop the pipeline |
| `GET` | `/api/pm/status` | Current run state and task counts |
| `POST` | `/api/pm/chat` | Send a message to the PM |
| `GET` | `/api/pm/events` | SSE stream of pipeline events |

### Tasks
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/tasks` | List all tasks |
| `POST` | `/api/tasks` | Create a task |
| `GET` | `/api/tasks/{id}` | Get a task |
| `PATCH` | `/api/tasks/{id}` | Update a task |
| `DELETE` | `/api/tasks/{id}` | Delete a task |

### Scheduler
| Method | Path | Auth | Description |
|---|---|---|---|
| `GET` | `/api/schedule` | None | List all schedules |
| `POST` | `/api/schedule` | None | Create a schedule |
| `PATCH` | `/api/schedule/{id}` | None | Enable/disable a schedule |
| `DELETE` | `/api/schedule/{id}` | None | Delete a schedule |

### Vault
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/vault/keys` | List all key names |
| `PUT` | `/api/vault/{key}` | Set a secret |
| `DELETE` | `/api/vault/{key}` | Delete a secret |

### Webhooks
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/webhooks` | List webhooks |
| `POST` | `/api/webhooks` | Add a webhook |
| `PATCH` | `/api/webhooks/{index}` | Update a webhook |
| `DELETE` | `/api/webhooks/{index}` | Delete a webhook |
| `POST` | `/api/webhooks/test/{index}` | Fire a test event |

### Config
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/config/agents` | Get all agent configs (model, provider, base_url) |
| `PATCH` | `/api/config/agents/{name}` | Update an agent's model/base_url |

### Setup (no auth required)
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/setup/status` | Check if `.env` is configured |
| `POST` | `/api/setup/init` | Write initial `.env` from wizard inputs |
| `GET` | `/api/setup/generate-key` | Generate a new Fernet-compatible vault key |

### Other
| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Health check (no auth) |
| `GET` | `/api/analytics` | Task completion stats |
| `GET` | `/api/restrictions` | Raw YAML content of restrictions file |
| `PATCH` | `/api/restrictions` | Save restrictions YAML |
| `GET` | `/api/templates` | List task templates |
| `GET` | `/api/git/status` | Git working tree status |
| `GET` | `/api/git/commits` | Recent commits |
| `GET` | `/api/workspace/{task_id}/files` | List workspace files for a task |
| `GET` | `/api/messaging/channels` | List notification channels |

---

## Configuration Files

All files live in `config/` (overridable via `HEIMDALL_CONFIG_DIR`).

### `config/settings.yaml`

Agent definitions, LLM parameters, and messaging adapter settings. Editable via Settings → AI Providers or directly.

```yaml
agents:
  worker:
    provider: ollama
    model: qwen3.5:35b-a3b-coding-nvfp4
    base_url: http://127.0.0.1:11434
    temperature: 0.3
    max_tokens: 8192
  reviewer:
    provider: anthropic
    model: claude-sonnet-4-6
    temperature: 0.1
    max_tokens: 4096
  orchestrator:
    provider: lmstudio
    model: gemma-3-27b
    base_url: http://127.0.0.1:1234
    temperature: 0.2
    max_tokens: 2048
```

### `config/restrictions.yaml`

Policy file enforced by the pipeline before any file operation. Editable live via Settings → Restrictions.

```yaml
protected_paths:
  - ".env"
  - "data/vault.json.enc"
write_allowed:
  - "workspace/**"
  - "tasks/**"
max_file_size: 5242880        # 5 MB
git_force_push: false
max_total_iterations_per_task: 10
```

### `config/templates.yaml`

Reusable task templates available in the New Task modal. Auto-created with defaults on first use.

---

## Data Directory

All runtime data lives in `data/` (overridable via `HEIMDALL_DATA_DIR`).

| File | Contents |
|---|---|
| `data/vault.json.enc` | Fernet-encrypted secrets store |
| `data/schedules.json` | Persisted cron schedule definitions |

---

## Workspace

Agent output stages to `workspace/current/<task-id>/`. Claude audits each output before it is promoted to the main codebase. Browse via GUI → Workspace or the API.

---

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

Test modules:
- `tests/test_vault.py` — Vault encryption/decryption
- `tests/test_task_manager.py` — Task CRUD and dependency resolution
- `tests/test_restrictions.py` — Policy enforcement
- `tests/test_routes_tasks.py` — Tasks REST API
- `tests/test_scheduler.py` — APScheduler integration
- `tests/test_analytics.py` — Analytics endpoint

---

## Linux Install (systemd)

```bash
sudo bash install.sh --host <your-server-ip-or-hostname>
```

What it does:
1. Checks Python 3.11+ and Node 18+
2. Creates `backend/.venv` and installs Python dependencies
3. Runs `npm install && npm run build` with `NEXT_PUBLIC_API_URL` set to the correct backend address (critical for remote access)
4. Copies `.env.example` → `.env` and writes `CORS_ORIGINS` for the server host
5. Installs **`heimdall-backend.service`** — FastAPI on `0.0.0.0:8000`
6. Installs **`heimdall-frontend.service`** — Next.js production server on port 3000
7. Both services enabled to start on boot
8. Installs `heimdall` CLI to `/usr/local/bin/`

### `heimdall` CLI

```bash
heimdall start          # start backend + frontend
heimdall stop           # stop frontend + backend
heimdall restart        # restart both
heimdall status         # systemctl status for both services
heimdall logs           # tail logs from both (Ctrl+C to exit)
heimdall logs-backend   # backend only
heimdall logs-frontend  # frontend only
heimdall open           # xdg-open http://<host>:3000
```

### Uninstall

```bash
sudo bash uninstall.sh           # remove services + CLI, keep data
sudo bash uninstall.sh --purge   # also delete .env, data/, vault, tasks/
```

---

## Server Deployment Notes

### AI connections from a remote server

All AI provider connections are outbound HTTP(S) from the backend. Configure them from **Settings → AI Providers**:

| Provider | Where configured | Notes |
|---|---|---|
| Anthropic (Claude) | Vault → `anthropic_key` | Outbound HTTPS to `api.anthropic.com` |
| OpenAI / Codex | Vault → `openai_key` | Outbound HTTPS to `api.openai.com` |
| Ollama | Settings → AI Providers → Worker `base_url` | Can be `http://other-server:11434` |
| LM Studio | Settings → AI Providers → Orchestrator `base_url` | Can be `http://other-server:1234` |

All edits to model names and base URLs are saved immediately to `config/settings.yaml` and take effect on the next pipeline run — no restart required.

### `NEXT_PUBLIC_API_URL`

This is baked into the frontend at build time. If you move the server or change its IP, rebuild the frontend:

```bash
cd frontend
NEXT_PUBLIC_API_URL="http://new-host:8000" npm run build
sudo systemctl restart heimdall-frontend
```

### CORS

The backend only accepts requests from origins listed in `CORS_ORIGINS` (in `.env`). Update it if you add a reverse proxy or change ports:

```bash
# .env
CORS_ORIGINS=http://192.168.1.50:3000,https://heimdall.mydomain.com
```

Then restart the backend: `sudo systemctl restart heimdall-backend`

### Reverse proxy (optional)

To serve both frontend and backend on port 80/443 via nginx:

```nginx
# /etc/nginx/sites-available/heimdall
server {
    listen 80;
    server_name heimdall.mydomain.com;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
    }

    # Backend API + SSE
    location /api/ {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Connection '';   # keep SSE connections alive
        proxy_buffering off;
        proxy_set_header Host $host;
    }
}
```

When using a reverse proxy, rebuild the frontend with the domain URL and update CORS:

```bash
NEXT_PUBLIC_API_URL=https://heimdall.mydomain.com npm run build
# CORS_ORIGINS=https://heimdall.mydomain.com  (in .env)
```

---

## Project Status & Roadmap

### Completed

| Phase | Feature | Status |
|---|---|---|
| B | Backend test suite (vault, tasks, restrictions, routes) | ✅ Done |
| C | Logs page, Workspace browser | ✅ Done |
| D | Startup scripts (`start_backend`, `start_frontend`, `setup.py`) | ✅ Done |
| E-1 | APScheduler + schedule CRUD API | ✅ Done |
| E-2 | Workspace file API (list, read, diff) | ✅ Done |
| E-3 | Analytics API + dashboard | ✅ Done |
| E-4 | Task templates (YAML-backed, modal selector) | ✅ Done |
| E-5 | Outbound webhooks (CRUD, HMAC signing, test fire) | ✅ Done |
| F | Schedule management page + sidebar link | ✅ Done |
| G | Restrictions YAML display fix + Webhook management UI | ✅ Done |
| I | Bearer token authentication + login page | ✅ Done |
| J | LLM provider config UI (agent model/base_url editor) | ✅ Done |
| K | Linux packaging (`install.sh`, systemd unit, `heimdall` CLI, setup wizard) | ✅ Done |
| L | Integration tests (scheduler, analytics) | ✅ Done |
| M | Docker Compose (backend + frontend services) | ✅ Done |
| — | First-run redirect flow (`AppShell`, `/setup` → `/login` → `/`) | ✅ Done |
| — | Analytics page fix (`api.analytics()`) | ✅ Done |

### Potential Future Work

| Feature | Notes |
|---|---|
| Multi-user auth | Currently single-token. Could add user accounts with role-based access. |
| Task dependencies UI | Dependency graph is supported in the data model but not visualised in the GUI. |
| Webhook edit (PATCH UI) | Backend supports `PATCH /api/webhooks/{index}` but no edit UI in settings yet. |
| Messaging channel test | No "send test message" button for Telegram/Discord/Email channels. |
| Dark/light theme toggle | Currently dark only. |
| Mobile layout | Sidebar collapses but layout is desktop-first. |
| Audit log page | All pipeline events are streamed via SSE and logged; no persistent audit log viewer. |
| Remote Ollama / LM Studio | Currently assumes local endpoints; no multi-host support. |

---

## Security Notes

- **Vault key** (`HEIMDALL_VAULT_KEY`) is the only master secret in `.env`. All other secrets are stored encrypted in `data/vault.json.enc`.
- **API token** is a static Bearer token. It is stored client-side in `localStorage`. For production, use a strong random value (`openssl rand -hex 32`).
- The `/api/setup/*` and `/api/schedule` endpoints are intentionally unauthenticated — setup must work before auth is configured, and the scheduler fires jobs server-side with no HTTP client.
- Never commit `.env` or `data/vault.json.enc` to version control. Both are in `.gitignore`.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, Uvicorn, Pydantic v2 |
| Frontend | Next.js 14, React 18, Tailwind CSS, lucide-react |
| Encryption | `cryptography` (Fernet) |
| Scheduling | APScheduler 3.x |
| LLM clients | `anthropic`, `httpx` (Ollama/LM Studio/OpenAI-compat) |
| Git | GitPython, PyGithub |
| Messaging | python-telegram-bot, discord.py, aiosmtplib, aioimaplib |
| Containers | Docker, Docker Compose |
| Tests | pytest, FastAPI TestClient |
