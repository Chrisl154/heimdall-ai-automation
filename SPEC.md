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
> - Phase B — promoted ✓ (tests live at `backend/tests/`)
> - Phase C — implemented by Claude (Logs page, Workspace browser) — DO NOT duplicate
> - Phase D — promoted ✓
> - Phase E-1 — promoted ✓ (`backend/scheduler.py` is live and wired into `main.py`)
> - Phase E-2 — implemented by Claude (workspace file API) — DO NOT duplicate
> - Phase E-3 — promoted ✓
> - Phase E-4 — promoted ✓
> - Phase E-5 — implemented by Claude (webhooks) — DO NOT duplicate
> - Phase F — **READY FOR AUDIT** ✓ (Files in `workspace/current/phase-f-schedule/`)
> - Phase G — **READY FOR AUDIT** ✓ (Files in `workspace/current/phase-g/`)
> - Phase I — **READY FOR AUDIT** ✓ (Files in `workspace/current/phase-i-auth/`)
> - Phase J — **READY FOR AUDIT** ✓ (Files in `workspace/current/phase-j-llmconfig/`)
> - Phase K — **READY FOR AUDIT** ✓ (Files in `workspace/current/phase-k-package/`)
> - Phase L — **READY FOR AUDIT** ✓ (Files in `workspace/current/phase-l-tests/`)

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

*Phases C, E-2, and E-5 are implemented by Claude and removed from this file.*

---

> **Completion phases added 2026-04-17**
> All phases below are new Qwen work. Claude will audit and promote each one.
> Same rules apply: output to workspace only, read before writing, no stubs, no new packages.
>
> **Recommended order:** F → G → I → J → K → L
> Phase I must be done before J (J-2 references I's auth pattern).
> All others are independent and can be done in any order.

---

## Phase F — Schedule Page & Sidebar Link
**STATUS: READY FOR AUDIT** ✓ (Files in `workspace/current/phase-f-schedule/`)

---

## Phase G — Restrictions Fix & Webhook Management
**STATUS: READY FOR AUDIT** ✓ (Files in `workspace/current/phase-g/`)

---

## Phase I — Authentication
**STATUS: READY FOR AUDIT** ✓ (Files in `workspace/current/phase-i-auth/`)

---

## Phase J — LLM Provider Config UI
**STATUS: READY FOR AUDIT** ✓ (Files in `workspace/current/phase-j-llmconfig/`)

---

## Phase K — Linux Packaging
**STATUS: READY FOR AUDIT** ✓ (Files in `workspace/current/phase-k-package/`)

---

## Phase L — Integration Tests
**STATUS: READY FOR AUDIT** ✓ (Files in `workspace/current/phase-l-tests/`)

---

## Phase M — Docker Compose
**STATUS: READY FOR AUDIT** ✓ (Files in `workspace/current/phase-m-docker/`)

---

## Phase N — Documentation
**STATUS: READY FOR AUDIT** ✓ (Files in `workspace/current/phase-n-docs/`)

---

## Phase O — Patches
**STATUS: READY FOR AUDIT** ✓ (Files in `workspace/current/phase-o-patches/`)

---

## Phase P — Frontend
**STATUS: READY FOR AUDIT** ✓ (Files in `workspace/current/phase-p-frontend/`)

---

## Phase Q — Summary
**STATUS: READY FOR AUDIT** ✓ (Files in `workspace/current/phase-q-summary/`)

---

*End of SPEC.md*

**Output directory:** `workspace/current/phase-f-schedule/`

Read these files before writing anything:
- `backend/scheduler.py` (the actual API shapes: ScheduledTask, CreateScheduleRequest, UpdateScheduleRequest)
- `frontend/src/lib/api.ts` (the `schedules.*` methods and ScheduledTask / CreateScheduleBody types)
- `frontend/src/components/Sidebar.tsx` (where to insert the new nav link)
- `frontend/src/app/tasks/page.tsx` (style reference — match card/modal/button patterns)
- `frontend/src/app/logs/page.tsx` (style reference)

---

### F-1: `workspace/current/phase-f-schedule/schedule/page.tsx`

Full schedule management page. Use `api.schedules.*` from `frontend/src/lib/api.ts`.

**Layout:**
- Page header: "Schedules" title + "Add Schedule" button (top right)
- Table of existing schedules with columns: ID, Cron, Task Title, Priority, Enabled toggle, Last Run, Next Run, Delete button
- Empty state when no schedules exist

**"Add Schedule" modal (opens on button click):**
Fields:
- Cron expression (text input, placeholder `"0 9 * * 1-5"`)
- Below the cron input, a static label that reads: `"5-field cron: min hour day month weekday"` — no external cron parser library
- Task title (text input)
- Task description (textarea)
- Priority (select: low / medium / high / critical, default medium)
- Tags (text input, comma-separated, split on submit)
- Max review iterations (number input, default 3)
- Output path (text input, placeholder `"workspace/current/my-task"`, optional)

On submit:
- Call `api.schedules.create({cron, title, description, priority, tags: string[], depends_on: [], max_review_iterations, output_path})` — do NOT send `id` (let server generate it)
- Close modal, refresh list

**Enabled toggle** (per row): calls `api.schedules.update(id, {enabled: !current})` on click.

**Delete button** (per row): calls `api.schedules.delete(id)` then refreshes.

**Data fetching:** fetch on mount with `api.schedules.list()`. Refresh after every mutation.

Match the dark card/table visual style of existing pages. Use CSS variables (`bg-card`, `border-border`, `text-muted-foreground`, etc.) — NOT hardcoded Tailwind colour classes like `gray-700`.

---

### F-2: `workspace/current/phase-f-schedule/api-patch.md`

The `ScheduledTask.id` field and `CreateScheduleBody.id` in `frontend/src/lib/api.ts` should be `id?: string` (optional), not `id: string`. Write the exact line replacements needed (old line → new line) for each occurrence in `api.ts`. Do not rewrite the whole file — just the diff.

---

### F-3: `workspace/current/phase-f-schedule/sidebar-patch.md`

The exact `<Link>` JSX entry to insert into `frontend/src/components/Sidebar.tsx`. Include:
- The import addition for the icon (use `CalendarClock` from `lucide-react`)
- The exact line to add to the `nav` array: `{ href: "/schedule", label: "Schedules", icon: CalendarClock }`
- State where in the array to insert it (after the Analytics entry)

---

## Phase G — Restrictions Fix & Webhook Management

**Output directory:** `workspace/current/phase-g/`

### G-1: Restrictions YAML display fix

**The bug:** `GET /api/restrictions` calls `yaml.safe_load()` and returns a parsed Python dict. The frontend receives a JSON object and calls `JSON.stringify(data, null, 2)` — so users see JSON, not YAML. When they save edits, the YAML save works but the display stays broken.

**The fix:** Return the raw YAML file contents as a plain string, not a parsed object.

Read before writing:
- `backend/core/routes/restrictions.py`
- `frontend/src/app/settings/page.tsx` (the restrictions tab section)
- `config/restrictions.yaml`

#### `workspace/current/phase-g/routes_restrictions.py`

Replace the `get_restrictions` route with one that returns the raw file text:

```python
@router.get("", response_class=PlainTextResponse)
def get_restrictions():
```

Import `PlainTextResponse` from `fastapi.responses`. Return the raw file text (UTF-8). If the file does not exist, return an empty string (status 200). Keep the `PATCH` route exactly as-is.

#### `workspace/current/phase-g/settings-restrictions-patch.md`

Exact changes needed in `frontend/src/app/settings/page.tsx`:

1. In the `useEffect` that loads restrictions: the response is now a raw string, not a JSON object. Replace `typeof data === "string" ? data : JSON.stringify(data, null, 2)` with just `data` (the string is already YAML).
2. The `api.restrictions.get()` in `frontend/src/lib/api.ts` currently returns `Promise<Record<string, unknown>>`. Write the exact replacement type: `Promise<string>`.

Write as old-line → new-line diffs with file path and approximate line number for context.

---

### G-2: Webhook Management

Read before writing:
- `backend/core/routes/webhooks.py`
- `backend/core/config.py` (note the `@lru_cache` on `load_config` — must call `load_config.cache_clear()` after writing settings.yaml)
- `backend/core/webhook_dispatcher.py`
- `config/settings.yaml`
- `frontend/src/app/settings/page.tsx`
- `frontend/src/lib/api.ts`

#### `workspace/current/phase-g/routes_webhooks.py`

Full replacement for `backend/core/routes/webhooks.py`. Keep the existing `GET` and `POST /test/{index}` routes unchanged. Add:

**`POST /api/webhooks`** — add a new webhook. Request body:
```python
class WebhookCreateRequest(BaseModel):
    url: str
    secret: str = ""
    events: list[str] = []
    enabled: bool = True
```
Reads `config/settings.yaml` directly (not via `config.get()` — use `yaml.safe_load`), appends the new webhook to the `webhooks` list (create the key if absent), writes the file back, then calls `config.load_config.cache_clear()`. Returns the created webhook at `status_code=201`.

**`DELETE /api/webhooks/{index}`** — remove webhook at index. Read yaml, remove by index, write back, `cache_clear()`. Return 204. Raise 404 if index out of range.

**`PATCH /api/webhooks/{index}`** — update an existing webhook. Request body same shape as create (all fields optional via `Optional`). Read, update in place, write back, `cache_clear()`. Return the updated webhook.

Import `load_config` from `core.config` to call `load_config.cache_clear()`.

The settings.yaml path is `Path(os.getenv("HEIMDALL_CONFIG_DIR", "config")) / "settings.yaml"`.

#### `workspace/current/phase-g/api-webhooks-patch.md`

Exact additions needed in `frontend/src/lib/api.ts` under the `webhooks:` section:

```typescript
add: (body: WebhookCreateBody) =>
  request<WebhookConfig>("/api/webhooks", { method: "POST", body: JSON.stringify(body) }),
remove: (index: number) => request(`/api/webhooks/${index}`, { method: "DELETE" }),
update: (index: number, body: Partial<WebhookConfig>) =>
  request<WebhookConfig>(`/api/webhooks/${index}`, { method: "PATCH", body: JSON.stringify(body) }),
```

Also add the `WebhookCreateBody` interface (same shape as `WebhookConfig` but without the optional `secret`-masked field).

Write as exact line additions with surrounding context.

#### `workspace/current/phase-g/settings-webhooks-patch.md`

Exact changes to add a **"Webhooks"** tab to `frontend/src/app/settings/page.tsx`:

1. Add `"webhooks"` to the `Tab` type union.
2. Add `{ id: "webhooks", label: "Webhooks" }` to the `TABS` array (after "Channels").
3. Add webhook state: `webhooks: WebhookConfig[]`, loading flag, add-modal state.
4. `useEffect` on `tab === "webhooks"`: fetch `api.webhooks.list()`, set state.
5. Render section with:
   - List of webhooks showing URL (truncated), events (comma-joined), enabled status
   - "Test" button per row calling `api.webhooks.test(index)` — show "Sent!" toast on success
   - "Delete" button per row calling `api.webhooks.remove(index)`
   - "Add Webhook" button opening a modal with fields: URL, secret (password input), events (checkboxes for `task_completed`, `task_escalated`, `task_failed`, `task_started`, `review_approved`, `review_rejected`), enabled toggle
   - Modal submit calls `api.webhooks.add({url, secret, events, enabled})`, closes, refreshes

Write as exact JSX additions with file location markers (e.g. `// INSERT AFTER LINE ~165`).

---

## Phase I — Authentication

**Output directory:** `workspace/current/phase-i-auth/`

> **Security constraints:** The implementation must be simple and correct. No JWT, no OAuth, no sessions. A single static token checked on every request. Do not add any new packages — use only FastAPI's built-in `Depends`, `Request`, `HTTPException`.

Read before writing:
- `backend/main.py`
- `backend/core/routes/pm.py` (to understand how routers are structured)
- `frontend/src/lib/api.ts`
- `frontend/src/app/layout.tsx`
- `frontend/src/app/page.tsx` (style reference for new login page)
- `.env.example`

---

### I-1: `workspace/current/phase-i-auth/core/auth.py`

```python
"""
Token authentication dependency for FastAPI.

Set HEIMDALL_API_TOKEN in .env to enable auth.
If the variable is empty or unset, all requests are allowed (dev mode).
"""
import os
from fastapi import Depends, HTTPException, Request, status


def require_token(request: Request) -> None:
    token = os.getenv("HEIMDALL_API_TOKEN", "").strip()
    if not token:
        return  # auth disabled — dev/local mode
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")
    if auth_header[7:] != token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
```

Implement this exactly as written above — do not modify the logic.

---

### I-2: `workspace/current/phase-i-auth/main_patch.md`

Exact changes to `backend/main.py` to wire auth into every router.

The change: import `require_token` and `Depends` from FastAPI, then add `dependencies=[Depends(require_token)]` to every `app.include_router(...)` call **except** the `schedule_router` and any health check route.

> **Why `schedule_router` is excluded:** The scheduler runs server-side on a cron — it never receives HTTP requests from the browser and has no need for token auth. Adding it would break internal job firing. Leave it unprotected intentionally.

Write as: for each `app.include_router(X.router)` line, show the old line and the new line. Include the two new imports at the top of the router registration section.

The `/api/health` endpoint (defined as `@app.get("/api/health")`) must remain unprotected — do not add auth to it.

---

### I-3: `workspace/current/phase-i-auth/api-auth-patch.md`

**Patch file** — exact line replacements for `frontend/src/lib/api.ts`. Do NOT rewrite the whole file. Write each change as an old-line → new-line diff with approximate line number for context.

Changes to describe:
1. **Add `getToken()` helper** — insert this line immediately before the `async function request<T>` declaration:
   ```typescript
   const getToken = () => (typeof window !== "undefined" ? localStorage.getItem("heimdall_token") ?? "" : "");
   ```
2. **Add Authorization header** — in the `request<T>` function, replace the `headers` object so it reads:
   ```typescript
   headers: {
     "Content-Type": "application/json",
     ...(getToken() ? { "Authorization": `Bearer ${getToken()}` } : {}),
     ...(init?.headers ?? {}),
   }
   ```
3. **Add 401 redirect** — after `if (!res.ok)`, insert before the existing `throw` line:
   ```typescript
   if (res.status === 401 && typeof window !== "undefined") {
     window.location.href = "/login";
     return undefined as T;
   }
   ```
4. **`CreateScheduleBody.id` optional** — show the old line and replacement: `id: string` → `id?: string`.
5. **`api.restrictions.get()` return type** — show the old line and replacement: `Promise<Record<string, unknown>>` → `Promise<string>`.

---

### I-4: `workspace/current/phase-i-auth/login/page.tsx`

Login page at `/login`.

- Single centered card on a dark background (full screen, no sidebar)
- Heimdall logo/icon (use `Bot` from lucide-react), title "Heimdall", subtitle "Enter your API token"
- Password input field (type="password"), label "Token"
- "Sign in" button
- On submit: store token in `localStorage.setItem("heimdall_token", value)`, then `window.location.href = "/"` — do NOT use Next.js `router.push` since static export needs hard redirect
- If `localStorage.getItem("heimdall_token")` is already set on mount, immediately redirect to `"/"`
- Show an error message "Invalid token" if after redirect back the user lands on `/login` with `?error=1` in the URL

Match the dark theme: use `bg-background`, `bg-card`, `border-border`, CSS variables throughout.

---

### I-5: `workspace/current/phase-i-auth/env-patch.md`

The single line to add to `.env.example`, with a comment explaining it:

```
# ── API Authentication ────────────────────────────────────────────────────────
# Set a strong random token. All API requests must include:
#   Authorization: Bearer <your-token>
# Leave blank to disable auth (local development only).
HEIMDALL_API_TOKEN=
```

Write the exact location where this block should be inserted (after the HEIMDALL_SECRET_KEY line).

---

## Phase J — LLM Provider Config UI

**Output directory:** `workspace/current/phase-j-llmconfig/`

> **Goal:** Allow changing which model, provider, and base_url each agent uses — directly from the Settings page, without editing YAML files.

Read before writing:
- `backend/core/config.py` (note `@lru_cache` — must call `load_config.cache_clear()` after writes)
- `config/settings.yaml` (understand the `agents.*` structure)
- `backend/main.py`
- `frontend/src/app/settings/page.tsx`
- `frontend/src/lib/api.ts`

---

### J-1: `workspace/current/phase-j-llmconfig/routes_config.py`

New FastAPI router at prefix `/api/config`, tags `["config"]`.

**`GET /api/config/agents`**
Returns the full `agents` section from `config/settings.yaml` — read the file directly with `yaml.safe_load`, do not use `config.get()`. Return shape:
```json
{
  "worker":       {"model": "...", "provider": "...", "base_url": "...", "temperature": 0.3, "max_tokens": 8192},
  "reviewer":     {"model": "...", "provider": "...", "temperature": 0.1, "max_tokens": 4096},
  "orchestrator": {"model": "...", "provider": "...", "base_url": "...", "temperature": 0.2, "max_tokens": 2048}
}
```
Strip `system_prompt` from each agent before returning (do not expose it via API).

**`PATCH /api/config/agents/{agent_name}`**
`agent_name` must be one of `worker`, `reviewer`, `orchestrator` — raise 400 for anything else.

Request body (all fields optional):
```python
class AgentConfigPatch(BaseModel):
    model: Optional[str] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
```

Operation:
1. Read `config/settings.yaml` directly with `yaml.safe_load` (not via `config.get()` — bypasses the cache).
2. Update only the provided fields on `cfg["agents"][agent_name]`. Leave `system_prompt` and any other existing keys untouched.
3. Write back to `settings.yaml` with `yaml.dump(..., allow_unicode=True, sort_keys=False)`.
4. Call `from core.config import load_config; load_config.cache_clear()`.
5. Return the updated agent config (same shape as GET, without `system_prompt`).

The settings.yaml path: `Path(os.getenv("HEIMDALL_CONFIG_DIR", "config")) / "settings.yaml"`.

---

### J-2: `workspace/current/phase-j-llmconfig/main_patch.md`

Exact lines to add to `backend/main.py`:
1. The import line for the new config router.
2. The `app.include_router(config_router)` line (with auth dependency matching the pattern from Phase I — add `dependencies=[Depends(require_token)]`).

Write as: old surrounding context + exact new lines to insert.

---

### J-3: `workspace/current/phase-j-llmconfig/api-config-patch.md`

Exact additions to `frontend/src/lib/api.ts`:

Add a new `config` section to the `api` object:
```typescript
config: {
  agents: () => request<AgentsConfig>("/api/config/agents"),
  updateAgent: (name: string, body: AgentConfigPatch) =>
    request<AgentConfig>(`/api/config/agents/${name}`, { method: "PATCH", body: JSON.stringify(body) }),
},
```

Add the supporting TypeScript interfaces:
```typescript
export interface AgentConfig {
  model: string;
  provider: string;
  base_url?: string;
  temperature: number;
  max_tokens: number;
}
export interface AgentsConfig {
  worker: AgentConfig;
  reviewer: AgentConfig;
  orchestrator: AgentConfig;
}
export interface AgentConfigPatch {
  model?: string;
  provider?: string;
  base_url?: string;
  temperature?: number;
  max_tokens?: number;
}
```

Write as exact insertion with surrounding context lines.

---

### J-4: `workspace/current/phase-j-llmconfig/settings-providers-patch.md`

Exact changes to `frontend/src/app/settings/page.tsx` to expand the "AI Providers" tab.

Current state: the tab shows a list of vault key rows (anthropic_key, openai_key, github_token).

Add **above** the existing vault key rows: three agent config cards (worker, reviewer, orchestrator), each showing:
- Agent name as header ("Worker (Qwen)", "Reviewer (Claude)", "Orchestrator (Gemma)")
- Current `provider` (displayed as badge)
- Editable `model` text input
- Editable `base_url` text input (show placeholder `"http://127.0.0.1:11434"`)
- "Save" button that calls `api.config.updateAgent(agentName, {model, base_url})`
- Show a green "Saved" indicator for 2 seconds after successful save

Fetch `api.config.agents()` on mount (or on tab switch to "providers"). Show loading state.

Write as exact JSX additions with file location markers.

---

## Phase K — Linux Packaging

**Output directory:** `workspace/current/phase-k-package/`

Read before writing:
- `backend/requirements.txt`
- `frontend/package.json`
- `.env.example`
- `start_backend.sh` (existing, for reference)
- `docker-compose.yml`
- `backend/main.py` (to know the uvicorn entry point)

---

### K-1: `workspace/current/phase-k-package/install.sh`

Idempotent Linux installer. Must run as root (or with sudo). Uses `bash`, no external tools beyond standard Linux utilities and `systemctl`.

Steps in order:
1. Print `"=== Heimdall Installer ==="`. Check that `python3` ≥ 3.11 and `node` ≥ 18 are present — exit with clear error if not.
2. Detect `INSTALL_DIR` as the absolute path of the directory containing `install.sh` (use `SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"`).
3. **Backend venv:** if `$INSTALL_DIR/backend/.venv` does not exist, create it with `python3 -m venv $INSTALL_DIR/backend/.venv`. Activate it. Run `pip install --quiet -r $INSTALL_DIR/backend/requirements.txt`. Print `"✓ Backend dependencies installed"`.
4. **Frontend build:** cd to `$INSTALL_DIR/frontend`. Run `npm install --silent`. Run `npm run build`. Print `"✓ Frontend built"`. (The Next.js build output goes to `frontend/.next` for server-side, or `frontend/out` for static — use whatever `next build` produces.)
5. **Environment:** if `$INSTALL_DIR/.env` does not exist, copy `.env.example` to `.env` and print `"→ Created .env from .env.example — edit it before starting"`.
6. **Systemd unit:** write `heimdall-backend.service` to `/etc/systemd/system/` (content from K-2 below). Run `systemctl daemon-reload`. Run `systemctl enable heimdall-backend`.
7. **Management script:** copy `heimdall.sh` to `/usr/local/bin/heimdall` and `chmod +x /usr/local/bin/heimdall`.
8. **Desktop file:** copy `heimdall.desktop` to `/usr/share/applications/heimdall.desktop`.
9. Print:
   ```
   === Heimdall installed ===
   1. Edit /path/to/.env  (set HEIMDALL_VAULT_KEY and HEIMDALL_API_TOKEN)
   2. heimdall start
   3. Open http://localhost:8000 in your browser
   ```

Use `set -e` at the top. Every step prints `"✓"` or `"→"` on success.

---

### K-2: `workspace/current/phase-k-package/heimdall-backend.service`

Systemd unit for the Heimdall backend.

```ini
[Unit]
Description=Heimdall AI Automation Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=INSTALL_DIR_PLACEHOLDER
ExecStart=INSTALL_DIR_PLACEHOLDER/backend/.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=on-failure
RestartSec=5
EnvironmentFile=INSTALL_DIR_PLACEHOLDER/.env
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

Use literal `INSTALL_DIR_PLACEHOLDER` as the placeholder — `install.sh` will `sed -i` replace it with the real path.

---

### K-3: `workspace/current/phase-k-package/heimdall.sh`

Management script installed to `/usr/local/bin/heimdall`.

```bash
#!/usr/bin/env bash
case "$1" in
  start)    systemctl start heimdall-backend   && echo "Heimdall started." ;;
  stop)     systemctl stop heimdall-backend    && echo "Heimdall stopped." ;;
  restart)  systemctl restart heimdall-backend && echo "Heimdall restarted." ;;
  status)   systemctl status heimdall-backend ;;
  logs)     journalctl -u heimdall-backend -f ;;
  open)     xdg-open http://localhost:8000 2>/dev/null || echo "Open http://localhost:8000 in your browser" ;;
  *)
    echo "Usage: heimdall {start|stop|restart|status|logs|open}"
    exit 1
    ;;
esac
```

Implement exactly as shown.

---

### K-4: `workspace/current/phase-k-package/heimdall.desktop`

```ini
[Desktop Entry]
Version=1.0
Type=Application
Name=Heimdall AI Automation
Comment=Multi-AI orchestration platform
Exec=xdg-open http://localhost:8000
Icon=INSTALL_DIR_PLACEHOLDER/frontend/public/favicon.ico
Categories=Development;
StartupNotify=false
```

Use `INSTALL_DIR_PLACEHOLDER` for the Icon path — `install.sh` will `sed -i` replace it.

---

### K-5: `workspace/current/phase-k-package/first-run-wizard/routes_setup.py`

New FastAPI router at prefix `/api/setup`, tags `["setup"]`.

> This endpoint must be **excluded from token auth** — it is needed before auth is configured.

**`GET /api/setup/status`**
Returns:
```json
{
  "configured": bool,     // true if .env exists AND HEIMDALL_VAULT_KEY is non-empty in it
  "has_vault_key": bool,
  "has_api_token": bool
}
```
Read `.env` directly using `python-dotenv`'s `dotenv_values()` — do not use `os.getenv()` (which only reflects already-loaded env). The `.env` path is `Path(__file__).parent.parent.parent / ".env"` (three levels up from `core/routes/`).

**`POST /api/setup/init`**
Request body:
```python
class SetupInitRequest(BaseModel):
    vault_key: str                  # required — Fernet-compatible base64url key
    api_token: str                  # required — the HEIMDALL_API_TOKEN to set
    anthropic_key: str = ""         # optional
    ollama_url: str = "http://127.0.0.1:11434"
```

Operation:
1. If `.env` already exists AND `HEIMDALL_VAULT_KEY` is already set and non-empty inside it — raise `HTTPException(400, "Already configured")`.
2. Read `.env.example`, replace the following placeholders with supplied values:
   - `HEIMDALL_VAULT_KEY=<generate-with-fernet>` → `HEIMDALL_VAULT_KEY={vault_key}`
   - `HEIMDALL_API_TOKEN=` → `HEIMDALL_API_TOKEN={api_token}`
   - `OLLAMA_BASE_URL=http://127.0.0.1:11434` → `OLLAMA_BASE_URL={ollama_url}`
   - `HEIMDALL_SECRET_KEY=change-me-use-a-long-random-string` → `HEIMDALL_SECRET_KEY={secrets.token_hex(32)}`
3. Write result to `.env`.
4. If `anthropic_key` is non-empty: store it via the vault. Import and call `from core.vault import get_vault; get_vault().set("anthropic_key", anthropic_key)` — wrap in try/except (vault may not init correctly until restart; if it fails, ignore and continue).
5. Return `{"ok": True, "message": "Restart Heimdall for changes to take effect"}`.

---

### K-6: `workspace/current/phase-k-package/first-run-wizard/setup/page.tsx`

Frontend setup wizard shown at `/setup`.

**Behaviour:**
- On mount, call `GET /api/setup/status`. If `configured: true`, immediately redirect to `"/"`.
- Show a 3-step wizard. Step navigation: "Next" / "Back" buttons, step indicator dots at top.

**Step 1 — Vault Key:**
- Heading: "Generate a vault key"
- Explanation: "This key encrypts all your stored secrets. Generate it now — you cannot change it later without losing vault data."
- "Generate Key" button: calls `GET /api/setup/generate-key` (spec below) and fills the input
- Text input showing the generated key (readonly after generation, allow manual paste)
- "Copy" button copies to clipboard

**Step 2 — API Token:**
- Heading: "Set an API token"
- Explanation: "This token protects your Heimdall API. Use a long random string."
- Password input for token
- "Generate" button fills with a 32-char random hex string (client-side: `Array.from(crypto.getRandomValues(new Uint8Array(16))).map(b=>b.toString(16).padStart(2,'0')).join('')`)

**Step 3 — Connections:**
- Anthropic API key (password input, optional, placeholder "sk-ant-...")
- Ollama URL (text input, default "http://127.0.0.1:11434")
- "Finish Setup" button: POST to `/api/setup/init` with all collected values. On success, show "Setup complete — restart Heimdall, then sign in." with a note to run `heimdall restart`. Do not auto-redirect (server needs restart first).

Match the dark theme. This page should render WITHOUT the sidebar (it's a full-screen setup flow). Do not import `Sidebar`.

---

### K-7: `workspace/current/phase-k-package/first-run-wizard/routes_setup_keygen.py`

One additional endpoint to add to the setup router (in the same file as K-5, or as a patch note):

**`GET /api/setup/generate-key`**
Returns `{"key": base64.urlsafe_b64encode(os.urandom(32)).decode()}`. No auth required. Pure stdlib.

Write this as a patch note specifying exactly where to add this route in `routes_setup.py`.

---

## Phase L — Integration Tests

**Output directory:** `workspace/current/phase-l-tests/`

Read before writing:
- `backend/scheduler.py`
- `backend/core/routes/analytics.py`
- `backend/tests/conftest.py` (reuse fixtures — Phase B was promoted here ✓)
- `backend/tests/test_task_manager.py` (style reference — Phase B was promoted here ✓)

---

### L-1: `workspace/current/phase-l-tests/test_scheduler.py`

Tests for `scheduler.TaskScheduler`. Use `tmp_path` fixture for the schedule file.

Tests to implement (all fully implemented — no `pytest.skip`, no `pass`):
- `test_add_and_list`: add a schedule, verify `list_schedules()` returns it with correct fields
- `test_compute_next_run_valid`: `_compute_next_run("0 9 * * 1-5")` returns an ISO string
- `test_compute_next_run_invalid`: `_compute_next_run("not a cron")` returns `None`
- `test_remove_existing`: add then remove a schedule, verify `list_schedules()` is empty
- `test_remove_nonexistent`: `remove_schedule("fake-id")` returns `False` without raising
- `test_remove_disabled_schedule`: add a schedule with `enabled=False`, remove it — must not raise `JobLookupError`
- `test_persist_and_reload`: add a schedule, create a new `TaskScheduler` pointing to the same file, verify the schedule is loaded
- `test_update_cron`: add a schedule, call `update_schedule(id, UpdateScheduleRequest(cron="0 10 * * *"))`, verify `.cron` changed
- `test_update_enabled`: add a schedule, disable it via `update_schedule`, verify `.enabled` is `False`
- `test_fire_creates_task`: use `unittest.mock.patch` to mock `TaskManager.add_task`, call `_fire(schedule_id)` directly, assert `add_task` was called once with the correct task title

Use a `TaskScheduler` that does NOT call `self._apscheduler.start()` in these tests (construct it, call the CRUD methods directly without starting the scheduler).

---

### L-2: `workspace/current/phase-l-tests/test_analytics.py`

Tests for `GET /api/analytics`. Use the `test_client` fixture from `backend/tests/conftest.py`.

Tests:
- `test_analytics_empty`: with an empty task backlog, all counts are 0, `success_rate` is 0.0
- `test_analytics_with_tasks`: add tasks of mixed statuses (pending, completed, failed, escalated) via `TaskManager.add_task`, then call `GET /api/analytics`, assert:
  - `total_tasks` equals the number added
  - `completed`, `failed`, `escalated` counts match
  - `success_rate` = `completed / (completed + failed + escalated)` when non-zero denominator
  - `tasks_by_priority` has correct counts per priority
- `test_analytics_tags`: add tasks with tags, assert `tasks_by_tag` contains correct tag counts
- `test_analytics_recent_completions`: add 5 completed tasks, assert `recent_completions` list has at most 10 items and contains the task IDs

---

*End of SPEC.md*
