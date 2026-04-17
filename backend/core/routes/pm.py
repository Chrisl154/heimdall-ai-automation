"""
PM control routes — start/stop/status + chat + SSE event stream.
"""
import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from core.models import ChatRequest, ChatResponse, PMStatusResponse
from core.pm_engine import get_pm

router = APIRouter(prefix="/api/pm", tags=["pm"])


@router.post("/start", response_model=PMStatusResponse)
async def start_pm():
    pm = get_pm()
    await pm.start()
    return pm.get_status()


@router.post("/stop", response_model=PMStatusResponse)
async def stop_pm():
    pm = get_pm()
    await pm.stop()
    return pm.get_status()


@router.get("/status", response_model=PMStatusResponse)
async def get_status():
    return get_pm().get_status()


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    pm = get_pm()
    reply = await pm.chat(body.message, session_id=body.session_id)
    return ChatResponse(reply=reply, session_id=body.session_id)


@router.get("/events")
async def event_stream():
    """Server-Sent Events stream for real-time pipeline updates."""
    pm = get_pm()
    queue = pm.subscribe()

    async def generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    data = event.model_dump_json()
                    yield f"data: {data}\n\n"
                except asyncio.TimeoutError:
                    yield "data: {\"type\":\"ping\"}\n\n"
        finally:
            pm.unsubscribe(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
