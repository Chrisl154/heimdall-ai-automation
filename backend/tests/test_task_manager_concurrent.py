"""Tests verifying TaskManager singleton and dependency DAG behaviour."""
import pytest

from core.task_manager import TaskManager, get_task_manager
from core.models import Task, TaskStatus, TaskPriority


@pytest.fixture(autouse=True)
def reset_singleton():
    """Ensure a fresh singleton for each test."""
    import core.task_manager as tm_mod
    tm_mod._task_manager = None
    yield
    tm_mod._task_manager = None


class TestSingleton:
    def test_returns_same_instance(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HEIMDALL_TASKS_DIR", str(tmp_path / "tasks"))
        a = get_task_manager()
        b = get_task_manager()
        assert a is b

    def test_different_from_new_instance(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HEIMDALL_TASKS_DIR", str(tmp_path / "tasks"))
        singleton = get_task_manager()
        fresh = TaskManager(tasks_dir=str(tmp_path / "tasks2"))
        assert singleton is not fresh


class TestAddAndGet:
    def test_added_task_is_retrievable(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HEIMDALL_TASKS_DIR", str(tmp_path / "tasks"))
        mgr = get_task_manager()
        task = Task(
            id="t-100",
            title="Singleton test",
            description="Check singleton consistency",
            priority=TaskPriority.MEDIUM,
            status=TaskStatus.PENDING,
            created_at="2026-05-07",
        )
        mgr.add_task(task)
        assert mgr.get_task("t-100") is not None
        assert mgr.get_task("t-100").title == "Singleton test"

    def test_task_visible_across_singleton_calls(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HEIMDALL_TASKS_DIR", str(tmp_path / "tasks"))
        mgr1 = get_task_manager()
        task = Task(
            id="t-200",
            title="Cross-call task",
            description="Must be visible via second get_task_manager() call",
            priority=TaskPriority.HIGH,
            status=TaskStatus.PENDING,
            created_at="2026-05-07",
        )
        mgr1.add_task(task)
        mgr2 = get_task_manager()
        assert mgr2.get_task("t-200") is not None


class TestDependencyDAG:
    def test_blocked_task_not_returned(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HEIMDALL_TASKS_DIR", str(tmp_path / "tasks"))
        mgr = get_task_manager()
        parent = Task(
            id="parent-1",
            title="Parent",
            description="Must complete first",
            priority=TaskPriority.MEDIUM,
            status=TaskStatus.PENDING,
            created_at="2026-05-07",
        )
        child = Task(
            id="child-1",
            title="Child",
            description="Depends on parent",
            priority=TaskPriority.MEDIUM,
            status=TaskStatus.PENDING,
            depends_on=["parent-1"],
            created_at="2026-05-07",
        )
        mgr.add_task(parent)
        mgr.add_task(child)

        # Only the parent should be returned — child is blocked
        next_task = mgr.get_next_task()
        assert next_task is not None
        assert next_task.id == "parent-1"

    def test_unblocked_after_parent_completes(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HEIMDALL_TASKS_DIR", str(tmp_path / "tasks"))
        mgr = get_task_manager()
        parent = Task(
            id="p-2",
            title="Parent 2",
            description="Must complete first",
            priority=TaskPriority.MEDIUM,
            status=TaskStatus.PENDING,
            created_at="2026-05-07",
        )
        child = Task(
            id="c-2",
            title="Child 2",
            description="Waits for p-2",
            priority=TaskPriority.MEDIUM,
            status=TaskStatus.PENDING,
            depends_on=["p-2"],
            created_at="2026-05-07",
        )
        mgr.add_task(parent)
        mgr.add_task(child)

        mgr.mark_completed("p-2", output="done")
        next_task = mgr.get_next_task()
        assert next_task is not None
        assert next_task.id == "c-2"
