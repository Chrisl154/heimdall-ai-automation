"""
APScheduler-backed task scheduler with FastAPI router.
"""
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.models import Task, TaskCreateRequest, TaskStatus
from core.task_manager import TaskManager

logger = logging.getLogger("heimdall.scheduler")

# ── Singleton ─────────────────────────────────────────────────────────────────

_instance: Optional["TaskScheduler"] = None


def get_scheduler() -> Optional["TaskScheduler"]:
    return _instance


def set_scheduler(s: "TaskScheduler") -> None:
    global _instance
    _instance = s


# ── Pydantic models ───────────────────────────────────────────────────────────

class ScheduledTask(BaseModel):
    id: str
    cron: str
    task_template: TaskCreateRequest
    enabled: bool = True
    last_run: Optional[str] = None
    next_run: Optional[str] = None


class CreateScheduleRequest(BaseModel):
    id: Optional[str] = None
    cron: str
    title: str
    description: str
    priority: str = "medium"
    tags: list[str] = []
    depends_on: list[str] = []
    max_review_iterations: int = 3
    output_path: str = ""


class UpdateScheduleRequest(BaseModel):
    cron: Optional[str] = None
    enabled: Optional[bool] = None
    task_template: Optional[TaskCreateRequest] = None


# ── TaskScheduler ─────────────────────────────────────────────────────────────

class TaskScheduler:
    def __init__(self, task_manager: TaskManager):
        self._task_manager = task_manager
        self._apscheduler = AsyncIOScheduler()
        self._schedules: dict[str, ScheduledTask] = {}
        self._schedule_file = Path("data/schedules.json")
        self._load_schedules()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load_schedules(self) -> None:
        if not self._schedule_file.exists():
            return
        try:
            with open(self._schedule_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return
            for item in data:
                try:
                    s = ScheduledTask(**item)
                    self._schedules[s.id] = s
                except Exception as exc:
                    logger.warning("Skipping malformed schedule entry: %s", exc)
        except Exception as exc:
            logger.warning("Failed to load schedules.json: %s", exc)

    def _save_schedules(self) -> None:
        self._schedule_file.parent.mkdir(parents=True, exist_ok=True)
        data = [s.model_dump() for s in self._schedules.values()]
        with open(self._schedule_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _compute_next_run(self, cron_expr: str) -> Optional[str]:
        try:
            if len(cron_expr.split()) != 5:
                return None
            trigger = CronTrigger.from_crontab(cron_expr)
            next_dt = trigger.get_next_fire_time(None, datetime.now(timezone.utc))
            if next_dt:
                return next_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception as exc:
            logger.warning("Cannot compute next_run for %r: %s", cron_expr, exc)
        return None

    # ── APScheduler wrappers ──────────────────────────────────────────────────

    def _add_apsjob(self, schedule: ScheduledTask) -> None:
        trigger = CronTrigger.from_crontab(schedule.cron)
        self._apscheduler.add_job(
            self._fire,
            trigger=trigger,
            id=schedule.id,
            args=[schedule.id],
            replace_existing=True,
        )

    def _remove_apsjob(self, schedule_id: str) -> None:
        try:
            self._apscheduler.remove_job(schedule_id)
        except Exception:
            pass  # job wasn't registered (schedule was disabled)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        for s in self._schedules.values():
            if s.enabled:
                self._add_apsjob(s)
        self._apscheduler.start()

    def stop(self) -> None:
        if self._apscheduler.running:
            self._apscheduler.shutdown()

    # ── Job callback ──────────────────────────────────────────────────────────

    def _fire(self, schedule_id: str) -> None:
        schedule = self._schedules.get(schedule_id)
        if not schedule or not schedule.enabled:
            return
        try:
            task_id = f"task-{uuid.uuid4().hex[:8]}"
            task = Task(
                id=task_id,
                title=schedule.task_template.title,
                description=schedule.task_template.description,
                priority=schedule.task_template.priority,
                status=TaskStatus.PENDING,
                created_at=self._now_iso(),
                tags=schedule.task_template.tags,
                depends_on=schedule.task_template.depends_on,
                max_review_iterations=schedule.task_template.max_review_iterations,
                output_path=schedule.task_template.output_path or f"workspace/current/{task_id}",
            )
            self._task_manager.add_task(task)
            schedule.last_run = self._now_iso()
            schedule.next_run = self._compute_next_run(schedule.cron)
            self._save_schedules()
        except Exception as exc:
            logger.error("Failed to fire scheduled task %s: %s", schedule_id, exc)

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def list_schedules(self) -> list[ScheduledTask]:
        return list(self._schedules.values())

    def get_schedule(self, schedule_id: str) -> Optional[ScheduledTask]:
        return self._schedules.get(schedule_id)

    def add_schedule(self, schedule: ScheduledTask) -> ScheduledTask:
        schedule.next_run = self._compute_next_run(schedule.cron)
        self._schedules[schedule.id] = schedule
        if schedule.enabled:
            self._add_apsjob(schedule)
        self._save_schedules()
        return schedule

    def update_schedule(self, schedule_id: str, body: UpdateScheduleRequest) -> Optional[ScheduledTask]:
        schedule = self._schedules.get(schedule_id)
        if not schedule:
            return None

        needs_rejob = body.cron is not None or body.enabled is not None
        if needs_rejob:
            self._remove_apsjob(schedule_id)

        if body.cron is not None:
            schedule.cron = body.cron
            schedule.next_run = self._compute_next_run(body.cron)
        if body.enabled is not None:
            schedule.enabled = body.enabled
        if body.task_template is not None:
            schedule.task_template = body.task_template

        if needs_rejob and schedule.enabled:
            self._add_apsjob(schedule)

        self._save_schedules()
        return schedule

    def remove_schedule(self, schedule_id: str) -> bool:
        if schedule_id not in self._schedules:
            return False
        del self._schedules[schedule_id]
        self._remove_apsjob(schedule_id)
        self._save_schedules()
        return True


# ── Router ────────────────────────────────────────────────────────────────────

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


def _get() -> TaskScheduler:
    s = get_scheduler()
    if s is None:
        raise HTTPException(503, "Scheduler not initialised")
    return s


@router.get("", response_model=list[ScheduledTask])
def list_schedules():
    return _get().list_schedules()


@router.post("", response_model=ScheduledTask, status_code=201)
def create_schedule(body: CreateScheduleRequest):
    s = _get()
    schedule_id = body.id or f"sched-{uuid.uuid4().hex[:8]}"
    if s.get_schedule(schedule_id):
        raise HTTPException(409, f"Schedule {schedule_id!r} already exists")
    template = TaskCreateRequest(
        title=body.title,
        description=body.description,
        priority=body.priority,
        tags=body.tags,
        depends_on=body.depends_on,
        max_review_iterations=body.max_review_iterations,
        output_path=body.output_path,
    )
    return s.add_schedule(ScheduledTask(id=schedule_id, cron=body.cron, task_template=template))


@router.patch("/{schedule_id}", response_model=ScheduledTask)
def update_schedule(schedule_id: str, body: UpdateScheduleRequest):
    updated = _get().update_schedule(schedule_id, body)
    if not updated:
        raise HTTPException(404, f"Schedule {schedule_id!r} not found")
    return updated


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: str):
    if not _get().remove_schedule(schedule_id):
        raise HTTPException(404, f"Schedule {schedule_id!r} not found")
