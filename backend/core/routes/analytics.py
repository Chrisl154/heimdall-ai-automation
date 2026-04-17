"""Analytics routes for Heimdall."""
from collections import Counter
from datetime import datetime
from typing import Any

from fastapi import APIRouter

from core.task_manager import TaskManager

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _compute_stats() -> dict[str, Any]:
    mgr = TaskManager()
    tasks = mgr.list_tasks()

    total_tasks = len(tasks)
    completed = sum(1 for t in tasks if t.status.value == "completed")
    failed = sum(1 for t in tasks if t.status.value == "failed")
    escalated = sum(1 for t in tasks if t.status.value == "escalated")
    pending = sum(1 for t in tasks if t.status.value == "pending")

    success_rate = (completed / total_tasks * 100) if total_tasks > 0 else 0.0

    iterations_list = [
        t.current_iteration
        for t in tasks
        if t.status.value == "completed" and t.current_iteration > 0
    ]
    avg_iterations = sum(iterations_list) / len(iterations_list) if iterations_list else 0.0

    duration_pairs = [
        (t.started_at, t.completed_at)
        for t in tasks
        if t.status.value == "completed" and t.started_at and t.completed_at
    ]
    durations = []
    for started_str, completed_str in duration_pairs:
        try:
            started = datetime.fromisoformat(started_str.replace("Z", "+00:00"))
            completed_dt = datetime.fromisoformat(completed_str.replace("Z", "+00:00"))
            durations.append((completed_dt - started).total_seconds())
        except Exception:
            pass
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    priority_counts: dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for t in tasks:
        priority_counts[t.priority.value] = priority_counts.get(t.priority.value, 0) + 1

    tag_counts: Counter[str] = Counter()
    for t in tasks:
        for tag in t.tags:
            tag_counts[tag] += 1
    top_tags = dict(sorted(tag_counts.items(), key=lambda x: -x[1])[:8])

    recent_completions = [
        {
            "id": t.id,
            "title": t.title,
            "completed_at": t.completed_at or "",
            "iterations": t.current_iteration,
        }
        for t in sorted(tasks, key=lambda x: x.completed_at or "", reverse=True)
        if t.status.value == "completed"
    ][:5]

    return {
        "total_tasks": total_tasks,
        "completed": completed,
        "failed": failed,
        "escalated": escalated,
        "pending": pending,
        "success_rate": round(success_rate, 1),
        "avg_iterations": round(avg_iterations, 1),
        "avg_duration_seconds": round(avg_duration, 1),
        "tasks_by_priority": priority_counts,
        "tasks_by_tag": top_tags,
        "recent_completions": recent_completions,
    }


@router.get("")
def get_analytics():
    return _compute_stats()
