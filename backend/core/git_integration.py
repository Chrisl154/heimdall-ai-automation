"""
Git integration — stub pending qwen-006 implementation.
"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GitError(Exception):
    pass


class GitManager:
    """Stub — replace with qwen-006 output after review."""

    def __init__(self, repo_path: str = "."):
        self._repo_path = Path(repo_path)
        try:
            import git
            self._repo = git.Repo(repo_path, search_parent_directories=True)
        except Exception as exc:
            logger.warning("GitManager: could not open repo at %s: %s", repo_path, exc)
            self._repo = None

    def get_status(self) -> dict:
        if not self._repo:
            return {"branch": "unknown", "clean": True, "staged": [], "unstaged": []}
        try:
            return {
                "branch": self._repo.active_branch.name,
                "clean": not self._repo.is_dirty(untracked_files=True),
                "staged": [d.a_path for d in self._repo.index.diff("HEAD")],
                "unstaged": [d.a_path for d in self._repo.index.diff(None)],
            }
        except Exception as exc:
            logger.warning("get_status failed: %s", exc)
            return {"branch": "unknown", "clean": True, "staged": [], "unstaged": []}

    def commit_task_output(self, task_id: str, output_path: str, message: str) -> Optional[str]:
        if not self._repo:
            logger.warning("[Git] No repo — skipping commit.")
            return None
        try:
            self._repo.index.add([str(Path(output_path).resolve())])
            commit = self._repo.index.commit(message)
            logger.info("[Git] Committed %s: %s", task_id, commit.hexsha[:8])
            return commit.hexsha
        except Exception as exc:
            raise GitError(f"Commit failed: {exc}") from exc

    def get_current_branch(self) -> str:
        if not self._repo:
            return "unknown"
        try:
            return self._repo.active_branch.name
        except Exception:
            return "detached"

    def get_recent_commits(self, n: int = 10) -> list[dict]:
        if not self._repo:
            return []
        try:
            return [
                {
                    "sha": c.hexsha[:8],
                    "message": c.message.strip(),
                    "author": str(c.author),
                    "date": c.committed_datetime.isoformat(),
                }
                for c in list(self._repo.iter_commits(max_count=n))
            ]
        except Exception:
            return []

    def create_branch(self, name: str) -> None:
        if not self._repo:
            raise GitError("No git repo found.")
        try:
            self._repo.git.checkout("-b", name)
        except Exception as exc:
            raise GitError(f"Branch creation failed: {exc}") from exc

    def push(self, remote: str = "origin", branch: Optional[str] = None) -> None:
        from core.restrictions import check_git_push
        check_git_push(force=False)
        if not self._repo:
            raise GitError("No git repo found.")
        try:
            ref = branch or self._repo.active_branch.name
            self._repo.remote(remote).push(ref)
        except Exception as exc:
            raise GitError(f"Push failed: {exc}") from exc

    def create_github_pr(
        self,
        title: str,
        body: str,
        head: str,
        base: str,
        token: str,
        repo: str,
    ) -> str:
        try:
            from github import Github
            g = Github(token)
            gh_repo = g.get_repo(repo)
            pr = gh_repo.create_pull(title=title, body=body, head=head, base=base)
            return pr.html_url
        except Exception as exc:
            raise GitError(f"GitHub PR creation failed: {exc}") from exc
