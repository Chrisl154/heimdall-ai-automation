"""Tests for core.task_manager.TaskManager."""
import pytest

from core.models import Task, TaskStatus, TaskPriority
from core.task_manager import TaskManager


class TestTaskManagerLoad:
    def test_load_from_yaml(self, tmp_tasks_dir):
        tm = TaskManager(tasks_dir=str(tmp_tasks_dir))
        tasks = tm.list_tasks()
        assert len(tasks) == 3
        ids = {t.id for t in tasks}
        assert {"task-001", "task-002", "task-003"} == ids

    def test_load_empty_yaml(self, tmp_path):
        d = tmp_path / "tasks"
        d.mkdir()
        (d / "backlog.yaml").write_text("[]", encoding="utf-8")
        tm = TaskManager(tasks_dir=str(d))
        assert tm.list_tasks() == []


class TestGetNextTask:
    def test_returns_pending_task(self, tmp_tasks_dir):
        tm = TaskManager(tasks_dir=str(tmp_tasks_dir))
        task = tm.get_next_task()
        assert task is not None
        assert task.id == "task-001"
        assert task.status == TaskStatus.PENDING

    def test_returns_none_when_no_pending(self, tmp_tasks_dir):
        tm = TaskManager(tasks_dir=str(tmp_tasks_dir))
        tm.mark_completed("task-001", "done")
        # task-002 is in_progress, task-003 is completed — no pending left
        assert tm.get_next_task() is None

    def test_respects_depends_on(self, tmp_path):
        d = tmp_path / "tasks"
        d.mkdir()
        (d / "completed").mkdir()
        (d / "backlog.yaml").write_text(
            """\
- id: task-a
  title: "Task A"
  description: "Needs task-b first"
  priority: medium
  status: pending
  created_at: "2026-04-16"
  tags: []
  depends_on: [task-b]
  max_review_iterations: 3
  current_iteration: 0
  output_path: ""

- id: task-b
  title: "Task B"
  description: "No deps"
  priority: medium
  status: pending
  created_at: "2026-04-16"
  tags: []
  depends_on: []
  max_review_iterations: 3
  current_iteration: 0
  output_path: ""
""",
            encoding="utf-8",
        )
        tm = TaskManager(tasks_dir=str(d))
        # task-a has an unmet dep — task-b should come first
        assert tm.get_next_task().id == "task-b"
        tm.mark_completed("task-b", "done")
        # now task-a's dep is met
        assert tm.get_next_task().id == "task-a"


class TestMarkInProgress:
    def test_sets_status_and_started_at(self, tmp_tasks_dir):
        tm = TaskManager(tasks_dir=str(tmp_tasks_dir))
        tm.mark_in_progress("task-001")
        task = tm.get_task("task-001")
        assert task.status == TaskStatus.IN_PROGRESS
        assert task.started_at is not None

    def test_persists_across_instances(self, tmp_tasks_dir):
        tm = TaskManager(tasks_dir=str(tmp_tasks_dir))
        tm.mark_in_progress("task-001")
        tm2 = TaskManager(tasks_dir=str(tmp_tasks_dir))
        assert tm2.get_task("task-001").status == TaskStatus.IN_PROGRESS


class TestMarkCompleted:
    def test_writes_completed_file(self, tmp_tasks_dir):
        tm = TaskManager(tasks_dir=str(tmp_tasks_dir))
        tm.mark_completed("task-001", "output content")
        task = tm.get_task("task-001")
        assert task.status == TaskStatus.COMPLETED
        assert task.completed_at is not None
        completed = tmp_tasks_dir / "completed" / "task-001.md"
        assert completed.exists()
        assert completed.read_text(encoding="utf-8") == "output content"

    def test_persists_across_instances(self, tmp_tasks_dir):
        tm = TaskManager(tasks_dir=str(tmp_tasks_dir))
        tm.mark_completed("task-001", "done")
        tm2 = TaskManager(tasks_dir=str(tmp_tasks_dir))
        assert tm2.get_task("task-001").status == TaskStatus.COMPLETED


class TestMarkFailedEscalated:
    def test_mark_failed_sets_error(self, tmp_tasks_dir):
        tm = TaskManager(tasks_dir=str(tmp_tasks_dir))
        tm.mark_failed("task-001", "something went wrong")
        task = tm.get_task("task-001")
        assert task.status == TaskStatus.FAILED
        assert task.error == "something went wrong"

    def test_mark_escalated_sets_error(self, tmp_tasks_dir):
        tm = TaskManager(tasks_dir=str(tmp_tasks_dir))
        tm.mark_escalated("task-001", "human review needed")
        task = tm.get_task("task-001")
        assert task.status == TaskStatus.ESCALATED
        assert task.error == "human review needed"


class TestAddDeleteTask:
    def test_add_task_round_trip(self, tmp_tasks_dir):
        tm = TaskManager(tasks_dir=str(tmp_tasks_dir))
        new_task = Task(
            id="new-task",
            title="New Task",
            description="A new task",
            priority=TaskPriority.HIGH,
            status=TaskStatus.PENDING,
            created_at="2026-04-16",
        )
        tm.add_task(new_task)
        retrieved = tm.get_task("new-task")
        assert retrieved is not None
        assert retrieved.title == "New Task"

    def test_delete_task_removes_it(self, tmp_tasks_dir):
        tm = TaskManager(tasks_dir=str(tmp_tasks_dir))
        assert tm.delete_task("task-001") is True
        assert tm.get_task("task-001") is None

    def test_delete_nonexistent_returns_false(self, tmp_tasks_dir):
        tm = TaskManager(tasks_dir=str(tmp_tasks_dir))
        assert tm.delete_task("nonexistent") is False
