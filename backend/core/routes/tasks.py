"""
Task CRUD routes — list, create, update, delete.
"""
import asyncio
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from core.models import (
    Task,
    TaskCreateRequest,
    TaskPriority,
    TaskStatus,
    TaskUpdateRequest,
)
from core.task_manager import TaskManager

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

_mgr: TaskManager | None = None


def _get_mgr() -> TaskManager:
    global _mgr
    if _mgr is None:
        _mgr = TaskManager()
    return _mgr


@router.get("", response_model=list[Task])
def list_tasks():
    return _get_mgr().list_tasks()


@router.get("/{task_id}", response_model=Task)
def get_task(task_id: str):
    task = _get_mgr().get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    return task


@router.post("", response_model=Task, status_code=201)
async def create_task(body: TaskCreateRequest):
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    task = Task(
        id=task_id,
        title=body.title,
        description=body.description,
        priority=body.priority,
        status=TaskStatus.PENDING,
        created_at=now,
        tags=body.tags,
        depends_on=body.depends_on,
        max_review_iterations=body.max_review_iterations,
        output_path=body.output_path or f"workspace/current/{task_id}",
    )
    _get_mgr().add_task(task)
    from core.pm_engine import get_pm
    asyncio.create_task(get_pm().notify_task_added())
    return task


@router.patch("/{task_id}", response_model=Task)
def update_task(task_id: str, body: TaskUpdateRequest):
    mgr = _get_mgr()
    task = mgr.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    updates = body.model_dump(exclude_none=True)
    updated = mgr.update_task(task_id, **updates)
    return updated


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: str):
    if not _get_mgr().delete_task(task_id):
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
