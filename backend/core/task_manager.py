"""
Task manager stub.

Full implementation assigned to Qwen via task qwen-002 in tasks/backlog.yaml.
This stub provides the interface so the rest of the codebase compiles cleanly.
"""
import asyncio
import time
from pathlib import Path
from typing import Optional

import yaml

from core.models import ReviewResult, Task, TaskPriority, TaskStatus


class TaskManager:
    """Manages task state backed by tasks/backlog.yaml."""

    def __init__(self, tasks_dir: str = "tasks"):
        self._dir = Path(tasks_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        (self._dir / "completed").mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self._tasks: dict[str, Task] = {}
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        path = self._dir / "backlog.yaml"
        if not path.exists():
            return
        content = path.read_text(encoding="utf-8")
        needs_migration = False
        try:
            raw = yaml.safe_load(content) or []
        except yaml.constructor.ConstructorError:
            # File has Python object tags from a prior yaml.dump() — migrate
            print("[TaskManager] backlog.yaml has Python tags — migrating to clean format…")
            raw = yaml.unsafe_load(content) or []
            needs_migration = True
        if not isinstance(raw, list):
            return
        for item in raw:
            try:
                task = Task(**item) if isinstance(item, dict) else item
                self._tasks[task.id] = task
            except Exception as exc:
                print(f"[TaskManager] Skipping malformed task entry: {exc}")
        if needs_migration:
            self._flush()
            print("[TaskManager] Migration complete.")

    def _flush(self) -> None:
        path = self._dir / "backlog.yaml"
        # mode='json' serializes enums as plain strings — never writes Python object tags
        data = [t.model_dump(mode="json") for t in self._tasks.values()]
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_task(self, task_id: str) -> Optional[Task]:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[Task]:
        return list(self._tasks.values())

    def get_next_task(self) -> Optional[Task]:
        """Return the first pending task whose dependencies are all completed."""
        completed_ids = {t.id for t in self._tasks.values() if t.status == TaskStatus.COMPLETED}
        for task in self._tasks.values():
            if task.status != TaskStatus.PENDING:
                continue
            if all(dep in completed_ids for dep in task.depends_on):
                return task
        return None

    # ── State mutations ───────────────────────────────────────────────────────

    def _update(self, task_id: str, **kwargs) -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        for k, v in kwargs.items():
            setattr(task, k, v)
        self._flush()

    def mark_in_progress(self, task_id: str) -> None:
        self._update(task_id, status=TaskStatus.IN_PROGRESS, started_at=_now())

    def mark_in_review(self, task_id: str) -> None:
        self._update(task_id, status=TaskStatus.IN_REVIEW)

    def mark_fixing(self, task_id: str) -> None:
        self._update(task_id, status=TaskStatus.FIXING)

    def mark_completed(self, task_id: str, output: str) -> None:
        self._update(task_id, status=TaskStatus.COMPLETED, completed_at=_now())
        path = self._dir / "completed" / f"{task_id}.md"
        path.write_text(output, encoding="utf-8")

    def mark_failed(self, task_id: str, error: str) -> None:
        self._update(task_id, status=TaskStatus.FAILED, error=error)

    def mark_escalated(self, task_id: str, reason: str) -> None:
        self._update(task_id, status=TaskStatus.ESCALATED, error=reason)

    def set_iteration(self, task_id: str, n: int) -> None:
        self._update(task_id, current_iteration=n)

    def set_latest_output(self, task_id: str, output: str) -> None:
        self._update(task_id, latest_output=output)

    def set_latest_review(self, task_id: str, review: ReviewResult) -> None:
        self._update(task_id, latest_review=review)

    def add_task(self, task: Task) -> None:
        self._tasks[task.id] = task
        self._flush()

    def update_task(self, task_id: str, **kwargs) -> Optional[Task]:
        self._update(task_id, **kwargs)
        return self._tasks.get(task_id)

    def delete_task(self, task_id: str) -> bool:
        existed = task_id in self._tasks
        self._tasks.pop(task_id, None)
        if existed:
            self._flush()
        return existed


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
