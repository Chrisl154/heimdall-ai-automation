"""
Workspace file browser routes.

Lets the frontend inspect files Qwen wrote to workspace/current/<task_id>/.
"""
import difflib
import os
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from core.restrictions import check_path_read

router = APIRouter(prefix="/api/workspace", tags=["workspace"])

_SAFE_FILENAME = re.compile(r"^[a-zA-Z0-9_\-\.]+$")


def _workspace_root() -> Path:
    return Path(os.getenv("HEIMDALL_WORKSPACE_DIR", "workspace")) / "current"


def _task_dir(task_id: str) -> Path:
    if not re.match(r"^[a-zA-Z0-9_\-]+$", task_id):
        raise HTTPException(status_code=400, detail="Invalid task_id")
    path = _workspace_root() / task_id
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"No workspace for task '{task_id}'")
    return path


def _safe_file(task_dir: Path, filename: str) -> Path:
    if not _SAFE_FILENAME.match(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    resolved = (task_dir / filename).resolve()
    if not str(resolved).startswith(str(task_dir.resolve())):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")
    if not resolved.exists():
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found")
    return resolved


@router.get("/{task_id}/files")
def list_files(task_id: str):
    task_dir = _task_dir(task_id)
    files = sorted(
        f.name for f in task_dir.iterdir()
        if f.is_file() and _SAFE_FILENAME.match(f.name)
    )
    return {"task_id": task_id, "files": files}


@router.get("/{task_id}/file/{filename}")
def get_file(task_id: str, filename: str):
    task_dir = _task_dir(task_id)
    resolved = _safe_file(task_dir, filename)
    check_path_read(str(resolved), agent="reviewer")
    try:
        content = resolved.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Read error: {exc}")
    return {"task_id": task_id, "filename": filename, "content": content, "size_bytes": resolved.stat().st_size}


@router.get("/{task_id}/diff")
def diff_files(task_id: str, from_file: str, to_file: str):
    task_dir = _task_dir(task_id)
    a_path = _safe_file(task_dir, from_file)
    b_path = _safe_file(task_dir, to_file)
    check_path_read(str(a_path), agent="reviewer")
    check_path_read(str(b_path), agent="reviewer")
    a_lines = a_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    b_lines = b_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
    diff = "".join(difflib.unified_diff(a_lines, b_lines, fromfile=from_file, tofile=to_file))
    return {"task_id": task_id, "from_file": from_file, "to_file": to_file, "diff": diff}
