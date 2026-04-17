"""
Git status routes — read-only git info exposed to the frontend.
"""
from fastapi import APIRouter, HTTPException

from core.git_integration import GitManager, GitError

router = APIRouter(prefix="/api/git", tags=["git"])

_git: GitManager | None = None


def _get_git() -> GitManager:
    global _git
    if _git is None:
        _git = GitManager()
    return _git


@router.get("/status")
def git_status():
    try:
        return _get_git().get_status()
    except GitError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/commits")
def recent_commits(n: int = 10):
    try:
        return _get_git().get_recent_commits(n)
    except GitError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
