"""
System info and live update stream.
"""
import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/system", tags=["system"])
logger = logging.getLogger(__name__)

# Project root: backend/core/routes/system.py → ../../.. → backend/ → .. → project root
_INSTALL_DIR = Path(__file__).resolve().parent.parent.parent.parent


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(_INSTALL_DIR), *args],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout.strip()


@router.get("/info")
def system_info():
    """Return current version info and remote comparison."""
    try:
        sha     = _git("rev-parse", "--short", "HEAD")
        branch  = _git("rev-parse", "--abbrev-ref", "HEAD")
        message = _git("log", "-1", "--format=%s")
        author  = _git("log", "-1", "--format=%an")
        date    = _git("log", "-1", "--format=%ci")

        # Fetch quietly so behind/ahead counts are accurate
        subprocess.run(
            ["git", "-C", str(_INSTALL_DIR), "fetch", "--quiet"],
            capture_output=True, timeout=15,
        )
        behind_str = _git("rev-list", "--count", "HEAD..@{u}")
        ahead_str  = _git("rev-list", "--count", "@{u}..HEAD")

        return {
            "sha": sha,
            "branch": branch,
            "message": message,
            "author": author,
            "date": date,
            "commits_behind": int(behind_str) if behind_str.isdigit() else 0,
            "commits_ahead":  int(ahead_str)  if ahead_str.isdigit()  else 0,
            "install_dir": str(_INSTALL_DIR),
        }
    except Exception as exc:
        logger.warning("system_info failed: %s", exc)
        return {"sha": "unknown", "branch": "unknown", "message": str(exc),
                "commits_behind": 0, "commits_ahead": 0}


@router.get("/update")
async def update_stream():
    """
    SSE stream that runs the full update pipeline:
      1. git pull
      2. pip install (refresh deps)
      3. npm install + build (rebuild frontend)
      4. Restart service
    The connection drops when the service restarts — the client must poll
    /api/health until it recovers, then reload.
    """

    async def generator() -> AsyncGenerator[str, None]:

        def ev(msg: str, kind: str = "log") -> str:
            return f"data: {json.dumps({'type': kind, 'message': msg})}\n\n"

        async def run_cmd(
            cmd: list[str], cwd: str | None = None, timeout: int = 600
        ) -> tuple[int, str]:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            try:
                out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                return proc.returncode, out.decode(errors="replace")
            except asyncio.TimeoutError:
                proc.kill()
                return -1, "Timed out"

        yield ev("━━━ Heimdall Update ━━━", "step")

        # ── 1. git pull ───────────────────────────────────────────────────────
        yield ev("Pulling latest code from remote…", "step")
        rc, out = await run_cmd(["git", "-C", str(_INSTALL_DIR), "pull", "--ff-only"])
        for line in out.splitlines():
            if line.strip():
                yield ev(line)
        if rc != 0:
            yield ev(f"git pull failed (exit {rc}). Aborting.", "error")
            return

        already_current = "Already up to date" in out
        if already_current:
            yield ev("Already up to date — skipping rebuild.", "info")
            yield ev("No restart needed.", "info")
            yield ev("done", "done")
            return

        # ── 2. pip install ────────────────────────────────────────────────────
        venv_pip = _INSTALL_DIR / "backend" / ".venv" / "bin" / "pip"
        pip_bin = str(venv_pip) if venv_pip.exists() else (
            str(Path(sys.executable).parent / "pip")
        )
        req = str(_INSTALL_DIR / "backend" / "requirements.txt")

        yield ev("Updating Python dependencies…", "step")
        rc, out = await run_cmd([pip_bin, "install", "-r", req, "-q"])
        for line in out.splitlines():
            if line.strip():
                yield ev(line)
        if rc != 0:
            yield ev(f"pip install failed (exit {rc}). Aborting.", "error")
            return
        yield ev("Python dependencies ✓")

        # ── 3. npm install + build ────────────────────────────────────────────
        npm_bin = shutil.which("npm") or "npm"
        frontend_dir = str(_INSTALL_DIR / "frontend")

        yield ev("Installing frontend packages…", "step")
        rc, out = await run_cmd([npm_bin, "install", "--prefer-offline"], cwd=frontend_dir)
        for line in out.splitlines():
            if line.strip():
                yield ev(line)
        if rc != 0:
            yield ev(f"npm install failed (exit {rc}). Aborting.", "error")
            return
        yield ev("npm packages ✓")

        yield ev("Building frontend (this takes ~1-3 min)…", "step")
        host = os.getenv("HEIMDALL_HOST", "localhost")
        port = os.getenv("HEIMDALL_PORT", "8000")
        build_env = {
            **os.environ,
            "NEXT_PUBLIC_API_URL": os.getenv("NEXT_PUBLIC_API_URL", f"http://{host}:{port}"),
        }
        build_proc = await asyncio.create_subprocess_exec(
            npm_bin, "run", "build",
            cwd=frontend_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=build_env,
        )
        # Stream build output line by line
        assert build_proc.stdout is not None
        async for raw in build_proc.stdout:
            line = raw.decode(errors="replace").rstrip()
            if line.strip():
                yield ev(line)
        await build_proc.wait()
        if build_proc.returncode != 0:
            yield ev("Frontend build failed. Aborting.", "error")
            return
        yield ev("Frontend built ✓")

        # ── 4. Restart ────────────────────────────────────────────────────────
        yield ev("Restarting service…", "restarting")

        pid = os.getpid()
        svc_file = Path("/etc/systemd/system/heimdall-backend.service")
        if shutil.which("systemctl") and svc_file.exists():
            restart_cmd = "sudo systemctl restart heimdall-backend"
        else:
            # Dev mode: kill current process — uvicorn --reload will restart it
            restart_cmd = f"kill -TERM {pid}"

        subprocess.Popen(
            ["bash", "-c", f"sleep 3 && {restart_cmd}"],
            start_new_session=True,
            close_fds=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
