"""
Messaging channel routes — list, add, update, remove channels.
"""
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.models import ChannelType, MessagingChannel

router = APIRouter(prefix="/api/messaging", tags=["messaging"])

_manager = None


def set_manager(mgr) -> None:
    global _manager
    _manager = mgr


def _mgr():
    if _manager is None:
        raise HTTPException(status_code=503, detail="Messaging manager not initialised.")
    return _manager


@router.get("/channels")
def list_channels():
    return _mgr().list_channels()


class ChannelCreateRequest(BaseModel):
    type: ChannelType
    name: str
    targets: list[str] = []
    credentials: dict[str, str] = {}


@router.post("/channels", status_code=201)
async def add_channel(body: ChannelCreateRequest):
    ch = MessagingChannel(
        id=f"{body.type.value}-{uuid.uuid4().hex[:6]}",
        type=body.type,
        name=body.name,
        targets=body.targets,
        credentials=body.credentials,
    )
    mgr = _mgr()
    mgr.add_channel(ch)
    # Start the adapter immediately so it's live without a restart
    if ch.enabled:
        await mgr.start_channel(ch)
    return ch


class ChannelPatchRequest(BaseModel):
    enabled: bool | None = None
    name: str | None = None
    targets: list[str] | None = None


@router.patch("/channels/{channel_id}")
async def update_channel(channel_id: str, body: ChannelPatchRequest):
    mgr = _mgr()
    updates = body.model_dump(exclude_none=True)
    ch = mgr.update_channel(channel_id, **updates)
    if not ch:
        raise HTTPException(status_code=404, detail=f"Channel '{channel_id}' not found.")
    # Toggle adapter live without restart
    if "enabled" in updates:
        if ch.enabled:
            await mgr.start_channel(ch)
        else:
            await mgr.stop_channel(channel_id)
    return ch


@router.delete("/channels/{channel_id}", status_code=204)
async def delete_channel(channel_id: str):
    mgr = _mgr()
    await mgr.stop_channel(channel_id)
    if not mgr.remove_channel(channel_id):
        raise HTTPException(status_code=404, detail=f"Channel '{channel_id}' not found.")
