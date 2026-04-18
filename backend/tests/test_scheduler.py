"""Tests for scheduler.TaskScheduler — no APScheduler startup required."""
import json
from unittest.mock import patch

import pytest

from apscheduler.schedulers.asyncio import AsyncIOScheduler


def _make_scheduler(tmp_path):
    """Construct a TaskScheduler with an isolated schedule file, bypassing __init__."""
    from scheduler import TaskScheduler
    from core.task_manager import TaskManager

    s = object.__new__(TaskScheduler)
    s._task_manager = TaskManager()
    s._apscheduler = AsyncIOScheduler()
    s._schedules = {}
    s._schedule_file = tmp_path / "schedules.json"
    s._load_schedules()
    return s


def _make_schedule(cron="0 9 * * 1-5", title="Test Task", enabled=True):
    from scheduler import ScheduledTask
    from core.models import TaskCreateRequest

    return ScheduledTask(
        id="sched-001",
        cron=cron,
        task_template=TaskCreateRequest(
            title=title,
            description="desc",
            priority="medium",
            tags=[],
            depends_on=[],
            max_review_iterations=3,
            output_path="",
        ),
        enabled=enabled,
    )


def test_add_and_list(tmp_path):
    s = _make_scheduler(tmp_path)
    schedule = _make_schedule()
    s.add_schedule(schedule)

    result = s.list_schedules()
    assert len(result) == 1
    assert result[0].id == "sched-001"
    assert result[0].cron == "0 9 * * 1-5"
    assert result[0].task_template.title == "Test Task"


def test_compute_next_run_valid(tmp_path):
    s = _make_scheduler(tmp_path)
    result = s._compute_next_run("0 9 * * 1-5")
    assert result is not None
    assert "T" in result  # ISO format contains T separator


def test_compute_next_run_invalid(tmp_path):
    s = _make_scheduler(tmp_path)
    result = s._compute_next_run("not a cron")
    assert result is None


def test_remove_existing(tmp_path):
    s = _make_scheduler(tmp_path)
    s.add_schedule(_make_schedule())

    removed = s.remove_schedule("sched-001")
    assert removed is True
    assert s.list_schedules() == []


def test_remove_nonexistent(tmp_path):
    s = _make_scheduler(tmp_path)
    result = s.remove_schedule("fake-id")
    assert result is False


def test_remove_disabled_schedule(tmp_path):
    s = _make_scheduler(tmp_path)
    schedule = _make_schedule(enabled=False)
    s.add_schedule(schedule)

    # Must not raise JobLookupError even though the job was never registered
    removed = s.remove_schedule("sched-001")
    assert removed is True
    assert s.list_schedules() == []


def test_persist_and_reload(tmp_path):
    s1 = _make_scheduler(tmp_path)
    s1.add_schedule(_make_schedule())

    # New instance pointing to the same file
    s2 = _make_scheduler(tmp_path)
    result = s2.list_schedules()
    assert len(result) == 1
    assert result[0].id == "sched-001"


def test_update_cron(tmp_path):
    from scheduler import UpdateScheduleRequest

    s = _make_scheduler(tmp_path)
    s.add_schedule(_make_schedule())

    updated = s.update_schedule("sched-001", UpdateScheduleRequest(cron="0 10 * * *"))
    assert updated is not None
    assert updated.cron == "0 10 * * *"
    assert s.list_schedules()[0].cron == "0 10 * * *"


def test_update_enabled(tmp_path):
    from scheduler import UpdateScheduleRequest

    s = _make_scheduler(tmp_path)
    s.add_schedule(_make_schedule())

    updated = s.update_schedule("sched-001", UpdateScheduleRequest(enabled=False))
    assert updated is not None
    assert updated.enabled is False
    assert s.list_schedules()[0].enabled is False


def test_fire_creates_task(tmp_path):
    s = _make_scheduler(tmp_path)
    s.add_schedule(_make_schedule(title="Scheduled Job"))

    with patch.object(s._task_manager, "add_task") as mock_add:
        s._fire("sched-001")

    mock_add.assert_called_once()
    created_task = mock_add.call_args[0][0]
    assert created_task.title == "Scheduled Job"
