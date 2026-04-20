"""
Project summary route — aggregates git, task, and PM state for the Project dashboard.
"""
import logging
from pathlib import Path

from fastapi import APIRouter

from core.git_integration import GitManager, GitError
from core.task_manager import TaskManager
from core.models import TaskStatus

router = APIRouter(prefix="/api/project", tags=["project"])
logger = logging.getLogger(__name__)

_ACTIVE_STATUSES = {TaskStatus.IN_PROGRESS, TaskStatus.IN_REVIEW, TaskStatus.FIXING}


@router.get("/summary")
def project_summary():
    """Return a unified snapshot of git state and task queue for the Project dashboard."""
    git = GitManager()
    git_data: dict = {}
    try:
        status = git.get_status()
        commits = git.get_recent_commits(8)
        repo_name = Path(".").resolve().name
        git_data = {
            "repo": repo_name,
            "branch": status.get("branch", "unknown"),
            "clean": status.get("clean", True),
            "staged": status.get("staged", []),
            "unstaged": status.get("unstaged", []),
            "recent_commits": commits,
        }
    except GitError as exc:
        logger.warning("Git unavailable for project summary: %s", exc)
        git_data = {"repo": "unknown", "branch": "unknown", "clean": True, "staged": [], "unstaged": [], "recent_commits": []}

    tm = TaskManager()
    tasks = tm.list_tasks()

    active = [t for t in tasks if t.status in _ACTIVE_STATUSES]
    pending = [t for t in tasks if t.status == TaskStatus.PENDING]
    completed = [t for t in tasks if t.status == TaskStatus.COMPLETED]
    failed = [t for t in tasks if t.status == TaskStatus.FAILED]
    escalated = [t for t in tasks if t.status == TaskStatus.ESCALATED]

    def slim(t):
        return {"id": t.id, "title": t.title, "priority": t.priority, "status": t.status, "tags": t.tags}

    return {
        "git": git_data,
        "tasks": {
            "counts": {
                "active": len(active),
                "pending": len(pending),
                "completed": len(completed),
                "failed": len(failed),
                "escalated": len(escalated),
            },
            "active": [slim(t) for t in active],
            "next_up": [slim(t) for t in pending[:6]],
        },
    }
