"""Log retrieval routes — pipeline events (JSONL) and application log (text)."""
import json
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(prefix="/api/logs", tags=["logs"])

_EVENT_LOG = Path("logs/events.jsonl")
_APP_LOG = Path("logs/heimdall.log")


@router.get("/events")
def get_events(limit: int = 500):
    if not _EVENT_LOG.exists():
        return {"events": [], "total": 0}
    lines = _EVENT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    total = len(lines)
    events = []
    for line in lines[-limit:]:
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return {"events": events, "total": total}


@router.get("/app")
def get_app_log(lines: int = 300):
    if not _APP_LOG.exists():
        return {"lines": [], "exists": False}
    content = _APP_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
    return {"lines": content[-lines:], "exists": True, "total": len(content)}
