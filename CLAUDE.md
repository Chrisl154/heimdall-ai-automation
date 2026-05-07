# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend

```bash
# Start backend (creates venv, installs deps automatically)
bash start_backend.sh

# Manual setup
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py          # runs on http://localhost:8000 with --reload

# Run all tests
cd backend
pytest tests/ -v

# Run a single test file
pytest tests/test_vault.py -v

# Run a single test by name
pytest tests/test_vault.py::test_round_trip -v
```

### Frontend

```bash
# Start dev server
bash start_frontend.sh
# or manually:
cd frontend
npm install
npm run dev             # http://localhost:3000

# Build static export (required for production / systemd deploy)
cd frontend
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run build

# Lint
cd frontend
npm run lint
```

### Docker

```bash
cp .env.example .env    # then edit HEIMDALL_VAULT_KEY and HEIMDALL_API_TOKEN
docker compose up -d
```

## Architecture

Heimdall is a **three-agent AI pipeline** with a Next.js control plane:

```
Gemma (orchestrator/PM) — LM Studio — plans, routes tasks, handles chat
    ↓
Qwen (worker) — Ollama — executes tasks, writes files to workspace/
    ↓
Claude (reviewer) — Anthropic API — audits output, approves or requests fixes
```

The pipeline runs as a loop inside `PMEngine` (`backend/core/pm_engine.py`). It polls `tasks/backlog.yaml` via `TaskManager`, hands each pending task to `WorkflowEngine` (`backend/core/workflow_engine.py`), which implements the **Qwen → Claude review → fix** cycle. After Claude approves, PMEngine holds the output pending human commit approval before calling `GitManager`.

### Request flow

1. **Frontend** (`frontend/src/lib/api.ts`) — all API calls go through a single `request()` helper that attaches the Bearer token from `localStorage` and handles 401 redirects to `/login`.
2. **AppShell** (`frontend/src/components/AppShell.tsx`) — on every navigation, checks `GET /api/setup/status`; if unconfigured, redirects to `/setup`; if no token in localStorage, redirects to `/login`.
3. **FastAPI** (`backend/main.py`) — all routers registered with `Depends(require_token)` except `/api/setup/*` and `/api/schedule` (intentionally unauthenticated).
4. **SSE** — `GET /api/pm/events` streams `PipelineEvent` objects. Each browser tab gets its own `asyncio.Queue` via `PMEngine.subscribe()`.

### Key backend modules

| Module | Responsibility |
|---|---|
| `core/pm_engine.py` | Singleton `PMEngine` — task poll loop, SSE fan-out, chat, commit approval gate |
| `core/workflow_engine.py` | Qwen→Claude review loop; writes versioned output files to `workspace/current/<task_id>/` |
| `core/llm_providers.py` | `call_llm()` router — handles `anthropic`, `ollama`, `lmstudio`, `openai`, `openai_compat` with exponential backoff (5,10,20,40,80s) |
| `core/vault.py` | Fernet-encrypted secrets store; singleton `get_vault()` |
| `core/task_manager.py` | YAML-backed task CRUD; `get_next_task()` respects `depends_on` DAG |
| `core/restrictions.py` | Policy engine; `lru_cache`-backed rules from `config/restrictions.yaml`; call `reload()` after editing |
| `core/config.py` | `load_config()` reads `config/settings.yaml` and overlays `HEIMDALL_*` env vars; `lru_cache` — call `load_config.cache_clear()` after saves |
| `scheduler.py` | APScheduler wrapper + FastAPI router; persists schedules to `data/schedules.json` |
| `core/auth.py` | `require_token` FastAPI dependency; empty `HEIMDALL_API_TOKEN` disables auth (dev mode) |

### Data flow for a task

1. Task created in `tasks/backlog.yaml` (via API or scheduler)
2. `PMEngine._run_loop()` calls `TaskManager.get_next_task()` → picks first `pending` task with satisfied deps
3. `WorkflowEngine.execute_task()` calls Qwen → writes `workspace/current/<id>/output_v1.md`
4. Calls Claude reviewer → parses JSON `{approved, summary, issues, feedback}`
5. If rejected, writes `review_v1.md` and calls Qwen again (up to `max_review_iterations`)
6. On approval, returns `TaskResult(completed)` → PMEngine calls `mark_completed()` and emits `COMMIT_APPROVAL_REQUESTED`
7. Human approves via GUI → `PMEngine.approve_commit()` → `GitManager.commit_task_output()`

### Config & secrets

- `config/settings.yaml` — agent definitions (model, provider, base_url, temperature, max_tokens). Editable live via Settings UI or `core/config.save_config()`. Cache clears automatically on save.
- `config/restrictions.yaml` — path/content/iteration policies per agent role. Editable live via Settings → Restrictions.
- `data/vault.enc` — Fernet-encrypted secrets (Anthropic key, GitHub token, bot tokens). Never stored in `.env`. Access via `vault.get("anthropic_key")`.
- `.env` — only `HEIMDALL_VAULT_KEY`, `HEIMDALL_API_TOKEN`, `HEIMDALL_SECRET_KEY`, and infra overrides.

### Frontend structure

- `frontend/src/lib/api.ts` — all typed API calls and SSE helper. All types defined at the bottom of this file.
- `frontend/src/components/AppShell.tsx` — layout wrapper with auth redirect guard.
- `frontend/src/app/*/page.tsx` — one file per route, no shared page state.
- `next.config.js` uses `output: "export"` — the build produces a static site in `frontend/out/` that FastAPI serves in production. During development, Next.js dev server proxies to the backend via `NEXT_PUBLIC_API_URL`.

### SPEC.md workflow

`SPEC.md` defines **work phases** for the Qwen worker. Each phase has:
- A named output directory under `workspace/current/<phase-id>/`
- Files Qwen must read before writing
- Exact output filenames — no extras

Claude's role is to **audit** completed phases and **promote** output to the live codebase. When SPEC.md says a phase is "READY FOR AUDIT", read the output files, verify they meet the spec, then copy them to their canonical locations.

### Singleton pattern

Both `PMEngine` and `Vault` use module-level singletons (`get_pm()`, `get_vault()`). Tests must reset them: `core.pm_engine._pm = None` and `core.vault._vault = None` before each test that uses `TestClient`. See `backend/tests/conftest.py` for the pattern.

### Claude rate limiting

`WorkflowEngine._call_reviewer()` detects Anthropic 429 responses. After all retries are exhausted, it raises `ClaudeRateLimitError` and auto-approves the task with `summary="__rate_limited__"`. PMEngine then pauses Claude for 30 minutes (`_claude_unavailable_until`). Check for this sentinel value before interpreting review results.

### Auth pattern

`core/auth.py` exposes `require_token` — a FastAPI dependency that validates the `Authorization: Bearer <token>` header against `HEIMDALL_API_TOKEN`. When the env var is empty or unset, auth is disabled (dev mode). All routers in `main.py` are registered with `dependencies=[Depends(require_token)]` except `/api/setup/*`. Token comparison uses `hmac.compare_digest()` (timing-safe).

### Webhook dispatcher

`core/webhook_dispatcher.py` persists webhook configs in `data/webhooks.json`. On task completion `PMEngine` calls `WebhookDispatcher.dispatch(event, payload)` which fans out HTTP POST to all enabled URLs via `httpx.AsyncClient`. Secrets are stored masked (only a SHA-256 prefix is shown in list responses). CRUD endpoints: `GET/POST /api/webhooks`, `PATCH/DELETE /api/webhooks/{idx}`, `POST /api/webhooks/{idx}/test`.

### Ollama thinking output

`_stream_ollama()` in `core/llm_providers.py` yields both a `"thinking"` chunk type and a `"text"` chunk type. Newer Ollama models (Qwen3, DeepSeek-R1) expose reasoning in a dedicated `message.thinking` field; older builds embed it as `<think>…</think>` inline in `message.content`. Both forms are extracted and surfaced. Callers that only want the final answer should filter for `chunk_type == "text"`.

### Messaging adapters

`core/messaging/` contains provider adapters (Telegram, Discord, Email). `MessagingManager` (singleton) starts/stops all adapters during lifespan and exposes `send(channel, text)`. Adapter credentials live in the vault (`telegram_bot_token`, `discord_webhook_url`, etc.). Adapters are lazy-initialized — missing credentials silently disable that adapter without crashing startup.
