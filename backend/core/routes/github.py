"""
GitHub integration — connect via PAT, browse repos, clone/pull, set active project.
"""
import logging
import os
import subprocess
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.config import load_config, save_config
from core.vault import Vault

router = APIRouter(prefix="/api/github", tags=["github"])
logger = logging.getLogger(__name__)

GH_API = "https://api.github.com"
_GH_HEADERS = {"Accept": "application/vnd.github.v3+json"}


def _projects_dir() -> Path:
    return Path(os.getenv("HEIMDALL_PROJECTS_DIR", str(Path.home() / "heimdall-projects")))


def _auth_headers(token: str) -> dict:
    return {**_GH_HEADERS, "Authorization": f"token {token}"}


class ConnectRequest(BaseModel):
    token: str


class CloneRequest(BaseModel):
    repo_full_name: str
    clone_url: str
    set_active: bool = True


class SetActiveRequest(BaseModel):
    path: str


@router.post("/connect")
async def connect_github(body: ConnectRequest):
    """Validate a GitHub PAT and save to vault."""
    token = body.token.strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token is required")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{GH_API}/user", headers=_auth_headers(token))
            if r.status_code == 401:
                return {"valid": False, "error": "Invalid or expired token"}
            if r.status_code != 200:
                return {"valid": False, "error": f"GitHub returned {r.status_code}"}
            user = r.json()
    except httpx.TimeoutException:
        return {"valid": False, "error": "Request timed out"}
    except httpx.NetworkError as exc:
        return {"valid": False, "error": str(exc)}

    Vault().set("github_token", token)
    return {
        "valid": True,
        "username": user.get("login"),
        "name": user.get("name"),
        "avatar_url": user.get("avatar_url"),
        "public_repos": user.get("public_repos", 0),
    }


@router.get("/status")
async def github_status():
    """Return connection status and active project."""
    token = Vault().get("github_token")
    active_project = load_config().get("active_project_path")

    if not token:
        return {"connected": False, "active_project": active_project}

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(f"{GH_API}/user", headers=_auth_headers(token))
            if r.status_code != 200:
                return {"connected": False, "active_project": active_project, "error": "Token invalid or expired"}
            user = r.json()
    except Exception:
        return {"connected": False, "active_project": active_project}

    return {
        "connected": True,
        "username": user.get("login"),
        "name": user.get("name"),
        "avatar_url": user.get("avatar_url"),
        "active_project": active_project,
    }


@router.delete("/disconnect")
def disconnect_github():
    """Remove the GitHub token from the vault."""
    vault = Vault()
    if vault.has("github_token"):
        vault.delete("github_token")
    return {"disconnected": True}


@router.get("/repos")
async def list_repos(page: int = 1, per_page: int = 30, sort: str = "updated"):
    """List the authenticated user's repos."""
    token = Vault().get("github_token")
    if not token:
        raise HTTPException(status_code=400, detail="GitHub not connected")

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(
                f"{GH_API}/user/repos",
                headers=_auth_headers(token),
                params={
                    "per_page": per_page,
                    "page": page,
                    "sort": sort,
                    "affiliation": "owner,collaborator,organization_member",
                },
            )
            r.raise_for_status()
            repos = r.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {exc.response.status_code}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return [
        {
            "full_name": repo["full_name"],
            "name": repo["name"],
            "description": repo.get("description") or "",
            "private": repo["private"],
            "language": repo.get("language"),
            "stars": repo.get("stargazers_count", 0),
            "updated_at": repo.get("updated_at"),
            "clone_url": repo["clone_url"],
            "ssh_url": repo["ssh_url"],
            "default_branch": repo.get("default_branch", "main"),
        }
        for repo in repos
    ]


@router.post("/clone")
async def clone_repo(body: CloneRequest):
    """Clone a repo (or pull if already cloned) and optionally set as active project."""
    token = Vault().get("github_token")

    clone_url = body.clone_url
    if token and clone_url.startswith("https://"):
        clone_url = clone_url.replace("https://", f"https://{token}@")

    repo_name = body.repo_full_name.split("/")[-1]
    projects_dir = _projects_dir()
    dest = projects_dir / repo_name
    projects_dir.mkdir(parents=True, exist_ok=True)

    try:
        if dest.exists() and (dest / ".git").exists():
            result = subprocess.run(
                ["git", "-C", str(dest), "pull", "--ff-only"],
                capture_output=True, text=True, timeout=120,
            )
            action = "pulled"
        else:
            result = subprocess.run(
                ["git", "clone", clone_url, str(dest)],
                capture_output=True, text=True, timeout=300,
            )
            action = "cloned"

        if result.returncode != 0:
            err = result.stderr
            if token:
                err = err.replace(token, "***")
            raise HTTPException(status_code=500, detail=f"git {action} failed: {err[:500]}")

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Clone timed out (> 5 min)")

    local_path = str(dest)

    if body.set_active:
        save_config({"active_project_path": local_path})

    return {
        "action": action,
        "local_path": local_path,
        "repo": body.repo_full_name,
        "active": body.set_active,
    }


@router.post("/set-active")
def set_active_project(body: SetActiveRequest):
    """Set the active project path in config."""
    path = body.path.strip()
    if not Path(path).exists():
        raise HTTPException(status_code=400, detail=f"Path does not exist: {path}")
    save_config({"active_project_path": path})
    return {"active_project_path": path}


@router.get("/active")
def get_active_project():
    """Return the currently active project path."""
    return {"active_project_path": load_config().get("active_project_path")}
