# Heimdall AI Automation — Work Phases for Qwen

This file is a self-contained spec for Qwen. Each phase is independent.

**How to use:** Tell Qwen — *"Read SPEC.md in the project root and execute Phase X in full."*

The project root is: `c:/Users/SPChr/Documents/GitHub/project-heimdall/AIAutomation`

All output goes to `workspace/current/<phase-id>/` — never directly into `backend/` or `frontend/`.
Claude audits and promotes once done.

## Non-negotiable rules (apply to every phase)

1. **Read before writing.** Every file listed under "Read before starting" must be read in full before writing a single line of output.
2. **Output directory only.** Never write to `backend/`, `frontend/`, or anywhere outside the phase output directory listed at the top of each phase.
3. **No extra files.** Only produce the exact files named in the spec. Do not create `__init__.py`, `README.md`, helper modules, or anything not explicitly listed.
4. **No stubs or TODOs.** Every function, route, and component must be fully implemented. Never leave `pass`, `TODO`, `raise NotImplementedError`, or placeholder comments in delivered code.
5. **Exact filenames.** Use the exact filename paths shown — including directory prefix (e.g. `workspace/current/phase-d-scripts/setup.py`). Do not rename or reorganise.
6. **No dependency drift.** Do not add `pip install` or `npm install` calls inside Python/TypeScript source files. Do not introduce new packages that are not already in `backend/requirements.txt` or `frontend/package.json`.

---

> **Status as of 2026-04-17**
> - Phase B — assigned to Qwen (in progress)
> - Phase C — implemented by Claude (Logs page, Workspace browser) — DO NOT duplicate
> - Phase D — available for Qwen
> - Phase E-1 — available for Qwen
> - Phase E-2 — implemented by Claude (workspace file API) — DO NOT duplicate
> - Phase E-3 — available for Qwen
> - Phase E-4 — available for Qwen
> - Phase E-5 — implemented by Claude (webhooks) — DO NOT duplicate

---

## Phase B — Pytest Test Suite

**Output directory:** `workspace/current/phase-b-tests/`

> **Constraints:** Produce only the files listed below. Do not create `__init__.py`, `pytest.ini`, `conftest.py` duplicates, or helper modules unless they appear in this list. Every test must be fully implemented — no `pytest.skip`, no `pass`, no placeholder asserts like `assert True`.

Read these files before writing anything:
- `backend/core/models.py`
- `backend/core/vault.py`
- `backend/core/task_manager.py`
- `backend/core/restrictions.py`
- `backend/core/routes/tasks.py`
- `backend/core/routes/vault.py`
- `backend/core/routes/pm.py`
- `backend/main.py`

---

### B-1: `workspace/current/phase-b-tests/conftest.py`

Shared pytest fixtures:
- `vault_env(monkeypatch, tmp_path)` — generates a fresh `Fernet` key, sets `HEIMDALL_VAULT_KEY` and `HEIMDALL_DATA_DIR` env vars pointing to `tmp_path`
- `tmp_tasks_dir(tmp_path)` — creates a minimal `backlog.yaml` (2–3 test tasks as a root YAML array) in `tmp_path/tasks/`
- `test_client(monkeypatch, tmp_path)` — returns a FastAPI `TestClient` wrapping `main.app`, with env vars patched so vault and tasks use `tmp_path`

---

### B-2: `workspace/current/phase-b-tests/test_vault.py`

Test every public method of `core.vault.Vault`:
- `set` / `get` / `require` / `delete` / `list_keys` / `has` / `bulk_set`
- `VaultError` raised when `HEIMDALL_VAULT_KEY` is an invalid Fernet key
- `VaultError` raised when the vault file exists but was encrypted with a different key
- Round-trip: set a value, create a new `Vault` instance from the same file, get the value back

---

### B-3: `workspace/current/phase-b-tests/test_task_manager.py`

Test `core.task_manager.TaskManager`:
- Load from a YAML with 3 tasks (pending, in_progress, completed)
- `get_next_task` returns `None` when all are non-pending
- `get_next_task` respects `depends_on` — task with unmet dep is skipped
- `mark_in_progress` sets `started_at` and updates status; flush is visible in a fresh `TaskManager` on the same dir
- `mark_completed` writes `tasks/completed/<id>.md`
- `mark_failed` / `mark_escalated` set the `error` field
- `add_task` then `get_task` round-trip
- `delete_task` removes from YAML

---

### B-4: `workspace/current/phase-b-tests/test_restrictions.py`

Patch `HEIMDALL_CONFIG_DIR` to a `tmp_path` with a custom `restrictions.yaml`.
Test each function with both passing and violating inputs:
- `check_path_read` — blocked by `protected_paths` glob
- `check_path_write` — blocked by `protected_paths`; also blocked when path not in `write_allowed`
- `check_content` — blocked when content contains a `blocked_patterns` string
- `check_file_size` — blocked when bytes exceed `max_file_size`
- `check_git_push(force=True)` — blocked when `git_force_push: false`
- `check_task_iterations` — blocked at or above `max_total_iterations_per_task`
- Call `restrictions.reload()` after mutating the YAML and verify the new rule takes effect

---

### B-5: `workspace/current/phase-b-tests/test_routes_tasks.py`

Use `test_client` fixture. Test the tasks REST API:
- `GET /api/tasks` — returns list
- `POST /api/tasks` with valid body — returns 201 with created task
- `GET /api/tasks/{id}` — returns the task
- `PATCH /api/tasks/{id}` with `{"status": "completed"}` — returns updated task
- `DELETE /api/tasks/{id}` — returns 204, subsequent GET returns 404
- `POST /api/tasks` with missing `title` — returns 422

---

## Phase D — Startup & Setup Scripts

**Output directory:** `workspace/current/phase-d-scripts/`

Read these files before writing anything:
- `.env.example`
- `backend/requirements.txt`
- `frontend/package.json`
- `config/settings.yaml`
- `docker-compose.yml`

---

### D-1: `workspace/current/phase-d-scripts/setup.py`

Interactive first-run setup. **Pure Python stdlib — zero third-party imports.** The script must run with a stock Python 3.11 installation before any `pip install`.

> **DO NOT import `cryptography`, `Fernet`, or any non-stdlib package.**
> Generate a Fernet-compatible key with stdlib only:
> ```python
> import base64, os
> key = base64.urlsafe_b64encode(os.urandom(32)).decode()
> ```

Checks (print ✓ or ✗ for each):
1. Python ≥ 3.11
2. Ollama reachable at `http://127.0.0.1:11434` (GET `/api/tags`, status 200)
3. LM Studio reachable at `http://127.0.0.1:1234` (GET `/v1/models`, status 200)

Always call `response.read()` after `conn.getresponse()` to drain the socket.

Prompts (use `getpass.getpass` so input is not echoed):
- `HEIMDALL_VAULT_KEY` — offer to auto-generate if left blank (use `base64.urlsafe_b64encode(os.urandom(32)).decode()`)
- `ANTHROPIC_API_KEY` — optional, press Enter to skip
- `GITHUB_TOKEN` — optional, press Enter to skip

Actions:
- Auto-generate `HEIMDALL_SECRET_KEY` using `secrets.token_hex(32)` — do not prompt for it.
- Read `.env.example` line by line. For each non-comment line that starts with `KEY=`, replace it if a value for `KEY` was collected. Leave all other lines unchanged.
- If `.env` already exists, ask before overwriting.
- At the end print:
  ```
  bash start_backend.sh        (Linux/macOS/WSL)
  start_backend.bat            (Windows CMD)

  bash start_frontend.sh       (Linux/macOS/WSL)
  start_frontend.bat           (Windows CMD)
  ```

---

### D-2 / D-3: `start_backend.sh` and `start_backend.bat`

Bash and Windows batch scripts to start the backend.

**Both scripts must:**
1. Resolve `PROJECT_ROOT` from the script's own location, then `cd` to `backend/`.
2. Create `.venv` if absent (`python -m venv .venv`). Exit with a clear error message if this fails.
3. Activate the venv (`source .venv/bin/activate` / `call .venv\Scripts\activate.bat`).
4. **Dependency detection (critical):** Re-run `pip install -r requirements.txt` whenever `requirements.txt` is newer than `.venv/requirements_installed` (or the marker is absent). After a successful install, update the marker:
   - Bash: `touch .venv/requirements_installed` (the `-nt` test detects staleness)
   - Bat: use PowerShell one-liner to compare `LastWriteTime`, then `copy /b requirements.txt .venv\requirements_installed`
5. Run `python main.py`.

**Bash-specific:** add `set -e` at top; trap SIGINT/SIGTERM to print a clean stop message.

**Bat-specific:** In `.bat` files, `python main.py` is the last line. Ctrl+C kills the python.exe process directly — **do not add any errorlevel check or cleanup block after `python main.py`**, it is unreachable and misleading.

---

### D-4 / D-5: `start_frontend.sh` and `start_frontend.bat`

Bash and Windows batch scripts to start the frontend.

**Both scripts must:**
1. Resolve `PROJECT_ROOT` from the script's own location, then `cd` to `frontend/`.
2. **Dependency detection (critical):** Re-run `npm install` whenever `package.json` (or `package-lock.json` if present) is newer than `node_modules/.install_ok` (or the marker is absent). After a successful install, touch/copy the marker.
   - Bash: use `-nt` file test; marker is `node_modules/.install_ok`
   - Bat: use PowerShell `LastWriteTime` comparison; marker is `node_modules\.install_ok`
3. Run `npm run dev`.

**Bat-specific:** Same as D-3 — `npm run dev` is the last line. Do not add unreachable code after it.

---

## Phase E-1 — Scheduled / Recurring Tasks

**Output:** `workspace/current/phase-e-scheduler/`

> **Constraints:** Produce only the four files listed below. Do not modify any existing backend or frontend source file. Do not introduce packages not already in `requirements.txt` (APScheduler is already listed). Implement every route and method fully.

Read before starting:
- `backend/core/models.py`
- `backend/core/task_manager.py`
- `backend/core/routes/tasks.py`
- `backend/main.py`
- `backend/requirements.txt` (APScheduler is already listed)

**Backend — `workspace/current/phase-e-scheduler/scheduler.py`**

A `TaskScheduler` class wrapping APScheduler's `AsyncIOScheduler`:

```python
class TaskScheduler:
    def __init__(self, task_manager: TaskManager): ...
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    def add_schedule(self, schedule: ScheduledTask) -> None: ...
    def remove_schedule(self, schedule_id: str) -> bool: ...
    def list_schedules(self) -> list[ScheduledTask]: ...
```

`ScheduledTask` model (define it in scheduler.py, do not modify models.py):
```python
class ScheduledTask(BaseModel):
    id: str
    cron: str           # standard 5-field cron expression
    task_template: TaskCreateRequest
    enabled: bool = True
    last_run: Optional[str] = None
    next_run: Optional[str] = None
```

When a schedule fires, call `task_manager.add_task(Task(...from template...))`.
Persist schedules to `data/schedules.json`.

**Backend — `workspace/current/phase-e-scheduler/routes_schedule.py`**

FastAPI router at prefix `/api/schedule`:
- `GET /api/schedule` — list all schedules
- `POST /api/schedule` — add a schedule, returns `ScheduledTask`
- `PATCH /api/schedule/{id}` — enable/disable
- `DELETE /api/schedule/{id}` — remove

**Frontend — `workspace/current/phase-e-scheduler/schedule/page.tsx`**

- Table of active schedules: ID, cron expression, task title, enabled toggle, last run, next run, delete button
- "Add Schedule" modal: cron expression input (with a human-readable preview label below it), task title, description, priority
- Calls `GET/POST/PATCH/DELETE /api/schedule`
- No external cron-parser library — just display the raw cron string

**Frontend — `workspace/current/phase-e-scheduler/sidebar-addition.md`**

The exact `<Link>` JSX entry to add to `frontend/src/components/Sidebar.tsx` for this page (path, label, icon name from lucide-react).

---

## Phase E-3 — Analytics Dashboard

**Output:** `workspace/current/phase-e-analytics/`

> **Constraints:** Produce only the three files listed below. No chart library — all visualisations are pure CSS/SVG. Do not use hardcoded Tailwind colour classes like `gray-700` or `blue-500`; use CSS variables (`bg-card`, `border-border`, `text-muted-foreground`, etc.) to match the existing dark theme. Implement the full fetch-and-render cycle — no mock data.

Read before starting:
- `backend/core/models.py`
- `backend/core/task_manager.py`
- `backend/core/routes/tasks.py`
- `frontend/src/lib/api.ts`
- `frontend/src/app/git/page.tsx` (style reference)

**Backend — `workspace/current/phase-e-analytics/routes_analytics.py`**

FastAPI router at prefix `/api/analytics`.

`GET /api/analytics` — compute and return:
```json
{
  "total_tasks": int,
  "completed": int,
  "failed": int,
  "escalated": int,
  "pending": int,
  "success_rate": float,
  "avg_iterations": float,
  "avg_duration_seconds": float,
  "tasks_by_priority": {"low": int, "medium": int, "high": int, "critical": int},
  "tasks_by_tag": {"tag": int, ...},
  "recent_completions": [{"id": str, "title": str, "completed_at": str, "iterations": int}]
}
```

Derive all stats from `TaskManager.list_tasks()`. No database needed.

**Frontend — `workspace/current/phase-e-analytics/analytics/page.tsx`**

Stats dashboard. All charts must be pure CSS/SVG — no chart library.

Sections:
1. **Summary cards row:** Total, Completed, Failed, Escalated, Success Rate %
2. **Bar chart:** Tasks by priority (4 bars, CSS height-based, labelled)
3. **Bar chart:** Tasks by tag (top 8 tags)
4. **Averages row:** Avg iterations to completion, Avg task duration
5. **Recent completions table:** ID, title, completed at, iterations

Fetch from `GET /api/analytics`. Match the dark card visual style from existing pages (use CSS vars: `bg-card`, `border-border`, `text-muted-foreground`, etc — NOT hardcoded `gray-*` Tailwind colours).

**Frontend — `workspace/current/phase-e-analytics/sidebar-addition.md`**

The exact `<Link>` entry to add to `Sidebar.tsx`.

---

## Phase E-4 — Task Templates

**Output:** `workspace/current/phase-e-templates/`

> **Constraints:** Produce only the three files listed below. Do not modify existing source files. The patch description in `tasks-page-patch.md` must be written as precise JSX diffs — exact lines to add and where, not vague prose like "add a dropdown somewhere".

Read before starting:
- `backend/core/models.py`
- `backend/core/routes/tasks.py`
- `frontend/src/app/tasks/page.tsx`
- `frontend/src/lib/api.ts`

**Backend — `workspace/current/phase-e-templates/routes_templates.py`**

FastAPI router at prefix `/api/templates`.

Templates are stored in `config/templates.yaml` (create the file if absent). Each template:
```yaml
- id: react-component
  label: "React Component"
  priority: medium
  tags: ["frontend", "react", "typescript"]
  max_review_iterations: 3
  description_template: |
    Implement the React component described below.
    Use TypeScript, Tailwind CSS, and lucide-react for icons.
    Export the component as default.

    Component spec:
    {{user_spec}}
```

Routes:
- `GET /api/templates` — list all templates
- `GET /api/templates/{id}` — get one template

**Default templates to include in `workspace/current/phase-e-templates/templates.yaml`:**
1. `react-component` — React/TypeScript/Tailwind component
2. `python-module` — Python module with type annotations and docstrings
3. `api-endpoint` — FastAPI route with Pydantic models
4. `bug-fix` — Fix a described bug with root cause analysis
5. `refactor` — Refactor described code for clarity and performance

**Frontend — `workspace/current/phase-e-templates/tasks-page-patch.md`**

A precise description of the changes needed in `frontend/src/app/tasks/page.tsx`:
- Add a template selector dropdown in the "New Task" modal (fetches `GET /api/templates` on open)
- When a template is selected, pre-fill `description` with its `description_template`, pre-fill `priority` and `tags`
- Write the exact JSX additions needed (clearly marked as additions vs replacements)

---

*End of SPEC.md — Phases C, E-2, and E-5 are implemented by Claude and removed from this file.*
